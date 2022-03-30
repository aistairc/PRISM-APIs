const SEC = 1000;
const CHECK_RESULT_DELAY = 5 * SEC; // DEBUG CHANGE THIS, TOO FAST FOR PRODUCTION!

const statusEL = $("#job-status");
const progressBarEl = $('#job-progress > div');
const resultsEL = $("#results");
const graph2DURLEL = $("#disease-network-2d-url");
const graph3DURLEL = $("#disease-network-3d-url");


function checkForResult() {
  fetch(pageData.statusURL)
    .then(response => response.json())
    .then(data => {
      progressBarEl.attr('aria-valuenow', data.current);
      progressBarEl.attr('aria-valuemax', data.total);
      progressBarEl.width(Math.round(100 * data.current / data.total) + "%");
      progressBarEl.text(`${data.current} / ${data.total}`);

      if (data.status === true) {
        statusEL.addClass("d-none");
        graph2DURLEL.attr("href", pageData.graph2DURL);
        graph3DURLEL.attr("href", pageData.graph3DURL);
        resultsEL.removeClass("d-none");
      } else {
        setTimeout(checkForResult, CHECK_RESULT_DELAY);
      }
    });
}


checkForResult();
