// RunPoller (10.EL.18, FE-RUN-01..03). State lives on this service, a singleton, rather
// than on PostsCtrl's own scope, so a running-indicator survives navigation away from and
// back to the Posts page while the backend's search-run thread is still working.
// Uses $q rather than a bare Promise (unlike the tracker's own code sketch) so the resolved
// value flows back through an Angular digest cycle instead of a native-Promise microtask
// that could otherwise leave the caller's view stale until some unrelated digest occurs.
angular.module('easymcfApp').factory('RunPoller', ['$interval', '$q', 'ApiClient', function ($interval, $q, ApiClient) {
  var state = { active: false, runId: null, status: null, outcomeCounts: null, errorDetail: null };
  var interval = null;
  var deferred = null;

  function parseCounts(raw) {
    // run_log.outcome_counts is stored TEXT/JSON-encoded (easymcf/services/search.py); the
    // generic read returns it as a raw string, never parsed server-side.
    if (!raw || typeof raw !== 'string') { return raw || null; }
    try { return JSON.parse(raw); } catch (e) { return null; }
  }

  function poll() {
    ApiClient.get('run_log', state.runId).then(function (run) {
      state.status = run.status;
      state.outcomeCounts = parseCounts(run.outcome_counts);
      state.errorDetail = run.error_detail;
      if (run.status !== 'running') {
        $interval.cancel(interval);
        interval = null;
        state.active = false;
        deferred.resolve(run);
      }
    });
  }

  return {
    state: state,
    start: function (runId) {
      if (interval) { $interval.cancel(interval); interval = null; }
      deferred = $q.defer();
      state.active = true; state.runId = runId; state.status = 'running'; state.outcomeCounts = null; state.errorDetail = null;
      interval = $interval(poll, 2000);
      return deferred.promise;
    },
    cancel: function () {
      if (interval) { $interval.cancel(interval); interval = null; }
      state.active = false;
    }
  };
}]);
