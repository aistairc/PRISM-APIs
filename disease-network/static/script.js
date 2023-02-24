const SEC = 1000;
const CHECK_RESULT_DELAY = 5 * SEC;
const CHECK_QUEUE_DELAY = 30 * SEC;

const abortButtonEl = $("#abort");
const statusEL = $("#job-status");
const progressEl = $('#job-progress');
const progressBarEl = $('#job-progress > div');
const resultsEL = $("#results");
const graphURLEL = $("#disease-network-url");
const remainingFilesEl = $("#remaining-files");


let finished = false;
abortButtonEl.click(evt => {
  navigator.sendBeacon(pageData.abortURL);
});


let checkQueueDelay = 1;
let remainingAtLoad = null, totalFilesToProcess;
function checkForResult() {
  fetch(pageData.statusURL)
    .then(response => response.json())
    .then(data => {
      if (data.queue) {
        const filesProcessedSoFar = data.current;
        if (remainingAtLoad === null) {
          remainingAtLoad = data.queue;
        }
        progressBarEl.attr('aria-valuemax', remainingAtLoad);
        progressBarEl.attr('aria-valuenow', remainingAtLoad - data.queue);
        progressBarEl.width(Math.round(100 * (remainingAtLoad - data.queue) / remainingAtLoad) + "%");
        remainingFilesEl.text(`${data.queue} file(s) in queue before yours`);
        setTimeout(checkForResult, checkQueueDelay);
        checkQueueDelay = CHECK_QUEUE_DELAY;
      } else if (data.aborted) {
        statusEL.text('Aborted');
        remainingFilesEl.text('');
        progressEl.hide();
        setTimeout(() => {
          window.location.replace(pageData.indexURL);
        }, 5000);
      } else {
        statusEL.text('We are now processing your data; please wait for a while longer...')
        progressBarEl.attr('aria-valuemax', data.total);
        progressBarEl.attr('aria-valuenow', data.current);
        progressBarEl.width(Math.round(100 * data.current / data.total) + "%");
        remainingFilesEl.text(`${data.current} / ${data.total} file(s) processed`);

        if (data.status === true) {
          window.location.replace(pageData.graphURL);
        } else {
          setTimeout(checkForResult, CHECK_RESULT_DELAY);
        }
      }
    })
    .catch(response => {
      statusEL.text('There was an error contacting the server. It might be down. Please try to refresh a little later.');
      remainingFilesEl.text('');
      progressEl.hide();
      abortButtonEl.hide();
    })
}


checkForResult();
