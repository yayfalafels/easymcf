// RunPoller (10.EL.18, 11.EL.14, FE-RUN-01..03). State lives on this service, a singleton, rather
// than on a page controller's own scope, so a running-indicator survives navigation away from and
// back to the page while the backend's run thread is still working.
// One channel per run_type (11.07): ARCH-RUN-03 allows one running search and one running apply per
// user at the same time, so the Posts page's search poll and the Applications page's apply poll must
// not cancel each other. `state`/`start(runId)` keep the search channel's original shape.
// Uses $q rather than a bare Promise (unlike the tracker's own code sketch) so the resolved
// value flows back through an Angular digest cycle instead of a native-Promise microtask
// that could otherwise leave the caller's view stale until some unrelated digest occurs.
angular.module('easymcfApp').factory('RunPoller', ['$interval', '$q', 'ApiClient', function ($interval, $q, ApiClient) {
  var POLL_MS = 2000;
  var channels = {};

  function channel(runType) {
    if (!channels[runType]) {
      channels[runType] = {
        state: { active: false, runId: null, status: null, outcomeCounts: null, errorDetail: null, run: null },
        interval: null, deferred: null
      };
    }
    return channels[runType];
  }

  function parseCounts(raw) {
    // run_log.outcome_counts is stored TEXT/JSON-encoded (easymcf/services/search.py, apply.py); the
    // generic read returns it as a raw string, never parsed server-side.
    if (!raw || typeof raw !== 'string') { return raw || null; }
    try { return JSON.parse(raw); } catch (e) { return null; }
  }

  function poll(ch) {
    ApiClient.get('run_log', ch.state.runId).then(function (run) {
      ch.state.run = run;
      ch.state.status = run.status;
      ch.state.outcomeCounts = parseCounts(run.outcome_counts);
      ch.state.errorDetail = run.error_detail;
      if (run.status !== 'running') {
        $interval.cancel(ch.interval);
        ch.interval = null;
        ch.state.active = false;
        ch.deferred.resolve(run);
      }
    });
  }

  return {
    state: channel('search').state,
    parseCounts: parseCounts,
    stateFor: function (runType) { return channel(runType).state; },
    isActive: function () {
      return Object.keys(channels).some(function (key) { return channels[key].state.active; });
    },
    start: function (runId, runType) {
      var ch = channel(runType || 'search');
      if (ch.interval) { $interval.cancel(ch.interval); ch.interval = null; }
      ch.deferred = $q.defer();
      angular.extend(ch.state, { active: true, runId: runId, status: 'running', outcomeCounts: null, errorDetail: null, run: null });
      ch.interval = $interval(function () { poll(ch); }, POLL_MS);
      poll(ch);
      return ch.deferred.promise;
    },
    cancel: function (runType) {
      var ch = channel(runType || 'search');
      if (ch.interval) { $interval.cancel(ch.interval); ch.interval = null; }
      ch.state.active = false;
    }
  };
}]);
