"use strict";

(() => {
  const commentDisplayDelay = 0;
  const commentFadeIn = 0;
  const commentFadeOut = 0;
  let visualizer, dispatcher;
  let disabled_types = {};
  let currentDocData, currentEntities, currentNormalizations;
  let commentFollows = true;
  let isMac = true;
  const modKey = isMac ? 'metaKey' : 'ctrlKey';
  const modKeyName = isMac ? 'Cmd' : 'Ctrl';
  const appName = window.location.pathname.replace(/\/$/, '').split('/').pop();

  head.js(
    urls.jquery,
    () => head.js(...urls.libraries, onReady)
  );

  function onReady() {
    Util.loadFonts = function() {};
    window.Configuration = {
      "abbrevsOn": true,
      "textBackgrounds": "striped",
      "visual": {
        "margin": {
          "x": 2,
          "y": 1
        },
        "arcTextMargin": 1,
        "boxSpacing": 1,
        "curlyHeight": 4,
        "arcSpacing": 9,
        "arcStartHeight": 19
      },
      "svgWidth": "100%",
      // "rapidModeOn": false,
      // "confirmModeOn": true,
      // "autorefreshOn": false,
      "typeCollapseLimit": 30
    };
    $('.waiting-ready').prop('disabled', false);
    dispatcher = new Dispatcher();
    visualizer = new Visualizer(dispatcher, 'svg');
    dispatcher.post('init');
    dispatcher.post('collectionLoaded', [collData]);

    dispatcher
      .on('resize', onResize)
      .on('hideComment', hideComment)
      .on('displaySpanComment', displaySpanComment)
      .on('click', onSVGClicked)
      .on('dblclick', showTextForm)
      .on('mousemove', onMouseMove);

    const $toggles = $('#toggles_list');
    const $window = $(window);
    const $all = $('#all_toggles');

    collData.entity_types.forEach(({name, labels}) => {
      disabled_types[name] = false;

      const $label = $('<label>')
      .appendTo($toggles);

      $('<input type="checkbox">')
      .appendTo($label)
      .prop('checked', true)
      .click(evt => {
        let enabled = evt.target.checked;
        disabled_types[name] = !enabled;

        let values = Object.values(disabled_types);
        if (values.every(v => !v)) {
          $all.prop({
            checked: true,
            indeterminate: false,
          });
        } else if (values.every(v => v)) {
          $all.prop({
            checked: false,
            indeterminate: false,
          });
        } else {
          $all.prop({
            checked: false,
            indeterminate: true,
          });
        }

        if ($('#svg').is(':visible')) renderCurrentData();
      });

      $('<span>')
      .text(labels[0] || name)
      .appendTo($label);
    });

    $all.click(evt => {
      let enabled = evt.target.checked;
      $('#toggles_list input').prop('checked', enabled);
      Object.keys(disabled_types).forEach(k => disabled_types[k] = !enabled);

      if ($('#svg').is(':visible')) renderCurrentData();
    });


    $('#btn_annotate').click(submit);
    $('#btn_cancel').click(showRender);
    $('#back')
      .click(showTextForm)
      .dblclick(clearTextForm);
    $('#info')
      .click(showHelp);
    $('#btn_clear').click(clearTextForm);
    $('#drop_samples').change(loadSample);
    $('#btn_input_file').change(loadTextFile);

    $('#text').keydown(evt => {
      if (evt.which == 13 && evt[modKey]) {
        submit(evt);
      } else if (evt.which == 27 && currentDocData) {
        showRender();
      }
    })
    .on('input', evt => {
      $('#drop_samples').val('');
    });
    $('.modkeyname').text(modKeyName);

    $('#settings-opener').click(evt => {
      $('#settings-opener, #toggles').toggleClass('open');
      evt.stopPropagation();
      evt.preventDefault();
    });

    $(document).click(evt => {
      if (!$('#toggles').hasClass('open') || $(evt.target).is('#toggles, #toggles *')) return;
      $('#settings-opener, #toggles').removeClass('open');
    });

    let displayCommentTimer = null;
    let commentDisplayed = false;
    const $commentPopup = $('#commentpopup');
    function displayComment(evt, target, comment, commentText, commentType) {
      let classes = [];
      if (commentType) {
        // label comment by type, with special case for default note type
        let commentLabel;
        if (commentType == 'AnnotatorNotes') {
          commentLabel = '<b>Note:</b> ';
        } else {
          commentLabel = '<b>'+Util.escapeHTML(commentType)+':</b> ';
        }
        comment += commentLabel + Util.escapeHTMLwithNewlines(commentText);
        classes.push('comment_' + commentType);
      }
      if (!commentFollows) {
        classes.push('fixed-comment');
      }
      $commentPopup[0].className = classes.join(' ');
      $commentPopup.html(comment);
      adjustToCursor(evt, $commentPopup, 10, true, true);
      clearTimeout(displayCommentTimer);
      /* slight "tooltip" delay to allow highlights to be seen
          before the popup obstructs them. */
      displayCommentTimer = setTimeout(function() {
        $commentPopup.stop(true, true).fadeIn(commentFadeIn);
        commentDisplayed = true;
      }, commentDisplayDelay);
    }

    const cursor = { x: 0, y: 0 };
    function adjustToCursor(evt, $element, offset, top, right) {
      if (evt) {
        cursor.x = evt.clientX;
        cursor.y = evt.clientY;
      }
      // get the real width, without wrapping
      $element.css({ left: 0, top: 0 });
      const screenHeight = $window.height();
      const screenWidth = $window.width();
      // FIXME why the hell is this 22 necessary?!?
      const elementHeight = $element.height() + 22;
      const elementWidth = $element.width() + 22;
      let x, y;
      offset = offset || 0;
      if (top) {
        y = cursor.y - elementHeight - offset;
        if (y < 0) top = false;
      }
      if (!top) {
        y = cursor.y + offset;
      }
      if (right) {
        x = cursor.x + offset;
        if (x >= screenWidth - elementWidth) right = false;
      }
      if (!right) {
        x = cursor.x - elementWidth - offset;
      }
      if (y < 0) y = 0;
      if (x < 0) x = 0;
      $element.css({ top: y, left: x });
    };

    function hideComment() {
      if (!commentFollows) return;
      clearTimeout(displayCommentTimer);
      if (commentDisplayed) {
        $commentPopup.stop(true, true).fadeOut(commentFadeOut, function() { commentDisplayed = false; });
      }
    }

    function onMouseMove(evt) {
      if (commentDisplayed && commentFollows) {
        adjustToCursor(evt, $commentPopup, 10, true, true);
      }
    }

    function displaySpanComment(
        evt, target, spanId, spanType, mods, spanText, commentText,
        commentType, normalizations) {

      if (!commentFollows) return;

      let comment = ( '<div><span class="comment_type_id_wrapper">' +
                      '<span class="comment_type">' +
                      Util.escapeHTML(Util.spanDisplayForm(collData.entity_types,
                                                            spanType)) +
                      '</span>' +
                      ' ' +
                      '<span class="comment_id">' +
                      'ID:'+Util.escapeHTML(spanId) +
                      '</span></span>' );
      if (mods.length) {
        comment += '<div>' + Util.escapeHTML(mods.join(', ')) + '</div>';
      }

      comment += '</div>';
      comment += ('<div class="comment_text">"' +
                  Util.escapeHTML(spanText) +
                  '"</div>');
      $.each(normalizations, function(normNo, norm) {
        let dbName = norm[0], dbKey = norm[1];
        comment += ( '<hr/>' +
                      '<a class="comment_id" href="https://uts.nlm.nih.gov//metathesaurus.html?cui=' + dbKey + '" target="uts_nlm_nih_gov">' +
                      'UMLS:' +
                      Util.escapeHTML(dbKey) + '</a>');
        let cuiName = currentDocData.cui_data[dbKey];
        if (cuiName) {
          comment += ('<br/><div>' + Util.escapeHTML(cuiName) + '</div>');
        }
      });

      displayComment(evt, target, comment, commentText, commentType);
    }


    function clearTextForm(evt) {
      $('#text').val('').focus();
    }

    function showTextForm() {
      commentFollows = true;
      hideComment();
      $('#svg, #spinner, #info_text').hide();
      $('#text_form').show();
      $('#text').focus();
    }

    function showRender() {
      $('#svg').show();
      $('#text_form, #spinner, #info_text').hide();
    }

    function showHelp() {
      if ($('#info_text').is(':visible')) {
        showTextForm();
      } else {
        $('#info_text').show();
        $('#text_form, #spinner, #svg').hide();
      }
    }

    function showSpinner() {
      commentFollows = true;
      hideComment();
      $('#svg, #text_form, #info_text').hide();
      $('#spinner').show();
    }

    function submit(evt) {
      const text = $('#text').val();
      if (!text.trim()) return;

      if (evt) {
        evt.stopPropagation();
        evt.preventDefault();
      }

      showSpinner();
      $.post(urls.annotate, {
        text: text,
      })
      .then(docData => {
        currentDocData = docData;
        currentEntities = docData.entities;
        currentNormalizations = {};
        docData.normalizations.forEach(norm => currentNormalizations[norm[0]] = norm)
        const time = new Date().toISOString();
        const name = appName + '-' + time.replace(/[-:]/g, '').replace('T', '_').replace(/\..*$/, '');
        $('#download-txt').removeClass('d-none').attr({
          href: datalink(docData.text),
          download: name + '.txt',
        });
        $('#download-ann').removeClass('d-none').attr({
          href: datalink(docData.annfile),
          download: name + '.ann',
        });
        showRender();
        renderCurrentData();
      });
      return false;
    }

    function loadTextFile() {
      var fr = new FileReader();
      fr.onload = function() {
        $('#text').val(fr.result).focus();
      }
      fr.readAsText(this.files[0]);
    }

    function loadSample(evt) {
      const pmid = evt.currentTarget.value;
      if (pmid) {
        $('#text').val(samples[pmid].body).focus();
      }
    }

    function renderCurrentData() {
      if (!currentDocData) return;
      $('#btn_cancel').prop('disabled', false);

      currentDocData.entities = currentEntities.filter(([id, name, spans]) => !disabled_types[name]);
      dispatcher.post('renderData', [currentDocData]);
    }

    function datalink(text) {
      const base64 = btoa(unescape(encodeURIComponent(text)));
      return "data:text/plain;charset=UTF-8;base64," + base64;
    }

    function resizeFunction(evt) {
      dispatcher.post('renderData');
    }

    let resizerTimeout = null;
    function onResize(evt) {
      if (evt.target === window) {
        clearTimeout(resizerTimeout);
        resizerTimeout = setTimeout(resizeFunction, 100); // TODO is 100ms okay?
      }
    }

    function onSVGClicked(evt) {
      const $target = $(evt.target);
      const spanId = $target.data('span-id');
      if (spanId && commentFollows) {
        $commentPopup.addClass('fixed-comment');
        commentFollows = false;
      } else {
        $commentPopup.removeClass('fixed-comment');
        commentFollows = true;
        hideComment();
      }
    }

    $('#spinner, #info_text').removeClass('d-none');
    showTextForm();
  } // onReady
})();
