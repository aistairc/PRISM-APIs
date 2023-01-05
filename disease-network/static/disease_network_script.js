// vim: ts=2 sts=2 sw=2 et ai

"use strict"



const regNames = {
  "-2": "Unspecified",
  "-1": "Negative",
  0: "Unregulated",
  1: "Positive",
  2: "Mixed",
}
const regColors = {
  "-2": "#aa6",
  "-1": "#c66",
  0: "#000",
  1: "#6c6",
  2: "#660",
}

const nodeColors = {
  Disorder: "#fa0",
}


head.js(
  urls.jquery,
  () => head.js(...urls.libraries, onReady)
);


let dispatcher
let focus
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
  const visualizer = new Visualizer(dispatcher, 'brat');
  dispatcher.post('init');
  dispatcher
    .on('resize', onResize)
    .on('doneRendering', onDoneRendering)

  let resizerTimeout = null;
  function resizeFunction(evt) {
    dispatcher.post('renderData');
  }
  function onResize(evt) {
    if (evt.target === window) {
      clearTimeout(resizerTimeout);
      resizerTimeout = setTimeout(resizeFunction, 100); // TODO is 100ms okay?
    }
  }

  function onDoneRendering() {
    if (focus) {
      let minY = null
      let el
      for (const focusItem of focus) {
        if (focusItem.length == 3) {
          el = $(`[data-arc-origin="${focusItem[0]}"][data-arc-role="${focusItem[1]}"][data-arc-target="${focusItem[2]}"]`)[0]
        } else {
          el = $(`[data-span-id="${focusItem[0]}"]`)[0]
        }
        const y = Math.max(
          el.parentNode.parentNode.parentNode.transform.baseVal[0].matrix.f
          + +el.getAttribute('y') - 20,
          0
        )
        if (!minY || y < minY) {
          minY = y
        }
      }
      $('#vis')[0].scrollTop = minY
    }
  }

  fetch(graphData)
  .then(res => res.json())
  .then(drawGraph)
}



let cy = null
function drawGraph(graph) {
  cy = cytoscape({
    container: document.getElementById('graph'),
    layout: {
      name: 'cose',
    },
    responsive: true,
    elements: {
      nodes: graph.nodes.map(data => ({
        data: {
          ...data,
          id: `n${data.id}`,
        }, 
      })),
      edges: graph.links.map(data => ({
        data: {
          ...data,
          id: `e${data.id}`,
          source: `n${data.source}`,
          target: `n${data.target}`,
        },
      })),
    },
    style: [
      {
        selector: 'node',
        style: {
          'background-color': 'blue',
          'font-size': 7,
          height: 10,
          width: 10,
          label: 'data(name)',
        }
      },
      {
        selector: 'node[type="..."]',
        style: {
          'background-color': 'magenta',
        }
      },
      {
        selector: 'node[type="Disorder"]',
        style: {
          'background-color': 'red',
        }
      },

      {
        selector: 'edge',
        style: {
          'font-size': 4,
          'text-rotation': 'autorotate',
          'target-arrow-shape': 'triangle',
          'line-opacity': 0.5,
          'curve-style': 'straight',
        }
      },
      {
        selector: 'edge[type]',
        style: {
          label: 'data(type)',
        },
      },
      ...Object.entries(regColors).map(([reg, color]) => ({
        selector: `edge[regulation=${reg}]`,
        style: {
          'line-color': color,
          'target-arrow-color': color,
        }
      })),
      {
        selector: '*:selected',
        style: {
          'underlay-color': 'yellow',
          'underlay-padding': 5,
          'underlay-shape': 'ellipse',
          'underlay-opacity': 1,
        },
      },
    ],
  })
  cy.remove(cy.nodes().filter('[[degree = 0]]'))

  // TODO XXX not really working
  let zoomInMargin
  let zoomOutMargin = 10
  function resize() {
    zoomInMargin = Math.min(
      cy.width() / 4,
      cy.height() / 4,
    )
  }
  resize()
  cy.on('resize', resize)

  // XXX DEBUG
  cy.on('select', 'node', function(evt) {
    displayNodeInfo(this)
  })
  cy.on('select', 'edge', function(evt) {
    displayEdgeInfo(this)
  })
  cy.on('unselect', '*', evt => displayNodeList())


  $('#tab-zoom-in-btn')
    .on('click', e => {
      const oldZoomAndPan = cy.pan()
      oldZoomAndPan.z = cy.zoom()
      cy.fit(cy.elements('*:selected'), zoomInMargin)
      const newZoomAndPan = cy.pan()
      newZoomAndPan.z = cy.zoom()
      if (oldZoomAndPan.x == newZoomAndPan.x
        && oldZoomAndPan.y == newZoomAndPan.y
        && oldZoomAndPan.z == newZoomAndPan.z
      ) {
        cy.fit(cy.elements(), zoomOutMargin)
      }
    })
  $('<span class="float-right textlink material-symbols-outlined">zoom_out</span>')

  window.cy = cy // DEBUG


  class Filter {
    constructor(items, prop, $element, callback) {
      this.prop = prop
      items = items.map(item => Array.isArray(item) ? item : [item, item])
      this.filter = Object.fromEntries(items.map(([value, name]) => [value, true]))
      for (const [value, name] of items) {
        const $label = $('<label/>')
          .appendTo($element)
        const $cb = $('<input type="checkbox" checked/>')
          .val(value)
          .on('change', evt => {
            this.filter[value] = evt.target.checked
            callback()
          })
          .appendTo($label)
        const $text = $('<span/>')
          .text(name)
          .appendTo($label)
      }
    }

    applyTo(instances) {
      return instances.filter(instance => this.filter[instance[this.prop]])
    }

    static applyTo(instances, filters) {
      return filters.reduce(
        (instances, filter) => filter.applyTo(instances),
        instances
      )
    }
  }

  function uniquePropValues(instances, prop) {
    const itemList = instances.map(instance => instance[prop])
    const items = [...new Set(itemList)]
    items.sort()
    return items
  }
  
  const allEdgeInstances = cy.edges().map(item => item.data('instances')).flat()

  const typeFilter = new Filter(
    uniquePropValues(allEdgeInstances, 'type'),
    'type', $('#relation-filters'), filtersChangedHandler
  )
  const regFilter = new Filter(
    uniquePropValues(allEdgeInstances, 'regulation').map(reg => [reg, regNames[reg]]),
    'regulation', $('#regulation-filters'), filtersChangedHandler
  )
  const docFilter = new Filter(
    uniquePropValues(allEdgeInstances, 'doc'),
    'doc', $('#document-filters'), filtersChangedHandler
  )
  const edgeFilters = [typeFilter, regFilter, docFilter]

  function singleVal(instances, prop, none, multi) {
    const valList = instances.map(instance => instance[prop])
    const valUniques = [...new Set(valList)]
    if (valUniques.length === 1) {
      return valUniques[0]
    } else {
      return valUniques.length ? multi : none
    }
  }

  let removedNodes = null;
  let removedEdges = null;
  function filtersChangedHandler() {
    if (removedEdges) {
      cy.add(removedNodes)
      cy.add(removedEdges)
    }
    select(null)
    cy.edges().forEach(edge => {
      const edgeData = edge.data()
      edgeData.filteredInstances = Filter.applyTo(edgeData.instances, edgeFilters)
      edgeData.regulation = singleVal(edgeData.filteredInstances, 'regulation', 0, 2)
      edgeData.type = singleVal(edgeData.filteredInstances, 'type', "", "...")
      edgeData.doc = singleVal(edgeData.filteredInstances, 'doc', "", "...")
      edge.data(edgeData)
    })

    removedEdges = cy.remove(cy.edges().filter(edge => !edge.data('filteredInstances').length))
    removedNodes = cy.remove(cy.nodes().filter('[[degree = 0]]'))

    cy.nodes().forEach(node => {
      const nodeData = node.data()
      nodeData.filteredInstances = docFilter.applyTo(nodeData.instances)
      nodeData.doc = singleVal(nodeData.filteredInstances, 'doc', "", "...")
      nodeData.type = singleVal(nodeData.filteredInstances, 'type', "", "...")
      node.data(nodeData)
    })

    const nodeList = cy.nodes().sort((a, b) => {
      let aa = a.data('name')
      let bb = b.data('name')
      if (aa.charAt(0) == '"') aa = aa.substring(1, aa.length - 2)
      if (bb.charAt(0) == '"') bb = bb.substring(1, aa.length - 2)
      return aa.localeCompare(bb)
    })
    const $nodeList = $('#node-list').empty()
    $('<h2/>')
      .text('Node List')
      .appendTo($nodeList)
    for (const node of nodeList) {
      $('<div class="textlink"/>')
        .text(node.data('name'))
        .on('click', evt => select(node))
        .appendTo($nodeList)
    }
  }
  filtersChangedHandler()

  function select(ele) {
    cy.elements('*:selected').unselect()
    if (ele) {
      ele.select()
    }
  }

  function displayNodeInfo(node) {
    $('#node-list').hide()
    $('#tab-info-cb').prop('checked', true)
    const $info = $('#info').empty()
    const nodeData = node.data()
    $('<h2/>')
      .text('Node Info')
      .appendTo($info)
    $('<h3/>')
      .text(nodeData.name)
      .appendTo($info)
    $('<a target="disease-network-cui"></a>')
      .attr('href', nodeData.url)
      .text(nodeData.cui)
      .appendTo($info)

    ![
      [node.outgoers(), "Influences", "target"],
      [node.incomers(), "Influenced by", "source"],
    ]
      .filter(([item]) => item.length)
      .forEach(([edges, name, otherEnd]) => {
        const $fs = $('<fieldset/>')
          .appendTo($info)
        $('<legend/>')
          .text(name)
          .appendTo($fs)
        edges.forEach(edge => {
          const otherNode = edge[otherEnd].bind(edge)()
          $('<div class="textlink"/>')
            .text(otherNode.data('name'))
            .on('click', evt => select(edge))
            .appendTo($fs)
        })
      })

    const $docFS = $('<fieldset/>')
      .appendTo($info)
    $('<legend/>')
      .text('Events')
      .appendTo($docFS)
    const $instances = $('<div/>')
      .appendTo($docFS)
    nodeData.filteredInstances.forEach(instance => {
      const $instance = $('<div/>')
        .appendTo($instances)
      $('<span class="textlink"/>')
        .text(instance.doc)
        .on('click', evt => displayDoc(instance.doc, instance.brat_ids))
        .appendTo($instance)
      $('<span/>')
        .text(" " + instance.type)
        .appendTo($instance)
    })
  }

  function displayEdgeInfo(edge) {
    $('#node-list').hide()
    $('#tab-info-cb').prop('checked', true)
    const $info = $('#info').empty()
    const edgeData = edge.data()
    const sourceData = edge.source().data()
    const targetData = edge.target().data()


    $('<h2/>')
      .text('Event Info')
      .appendTo($info)
    $('<h3/>')
      .text(edgeData.name)
      .appendTo($info)
    $('<div class="textlink"></div>')
      .text(edge.source().data().name)
      .on('click', e => select(edge.source()))
      .appendTo($info)
    $('<div>')
      .text('influences')
      .appendTo($info)
    $('<div class="textlink"></div>')
      .text(edge.target().data().name)
      .on('click', e => select(edge.target()))
      .appendTo($info)

    const classified = Object.fromEntries(
      Object.keys(regNames).map(reg => [reg, []])
    )
    edgeData.filteredInstances.forEach(d => classified[d.regulation].push(d))
    Object.entries(classified)
      .filter(([reg, instances]) => instances.length)
      .forEach(([reg, instances]) => {
        const $fs = $('<fieldset/>')
          .css('border-color', regColors[reg])
          .appendTo($info)
        $('<legend/>')
          .text(regNames[reg])
          .appendTo($fs)
        instances.forEach(instance => {
          const $instance = $('<div/>')
            .appendTo($fs)
          $('<div class="textlink">')
            .text(instance.doc)
            .on('click', evt => displayDoc(instance.doc, instance.brat_ids))
            .appendTo($instance)
          $('<span/>')
            .text(' ' + instance.type)
        })
      })
  }

  function displayDoc(doc, newFocus) {
    focus = newFocus
    console.log(newFocus)
    $('#vis').addClass('show')
    fetch(docDataBase + '/' + doc)
    .then(res => res.json())
    .then(currentDocData => {
      if (dispatcher) {
        dispatcher.post('current', [
          null,
          null,
          {
            focus,
          }
        ])
        dispatcher.post('collectionLoaded', [collData])
        dispatcher.post(
          'renderData',
          [currentDocData],
        )
      }
    })
  }

  function displayNodeList() {
    $('#node-list').show()
    $('#info').empty()
  }


  $('#download-json').on('click contextmenu', evt => {
    evt.target.href = "data:application/json," + encodeURIComponent(JSON.stringify(graph, null, 2))
  })
  $('#download-png').on('click contextmenu', evt => {
    evt.target.href = cy.png()
  })
  $('#download-svg').on('click contextmenu', evt => {
    window.b = cy.svg()
    evt.target.href = "data:application/json," + encodeURIComponent(cy.svg())
  })
}
