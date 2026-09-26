// AutomationCtrl (11.EL.18, page 8). One tab, Runs: every run_log row of the signed-in user, newest first, with
// type, track, times, status, and outcome counts. A row expands to its error detail and, for an apply run, the
// application rows it wrote. Session status lives in feature 17's global MCF pop-up, not here.
angular.module('easymcfApp').controller('AutomationCtrl', ['ApiClient', 'RunPoller', function (ApiClient, RunPoller) {
  var vm = this;
  vm.runs = []; vm.tracks = {}; vm.expanded = {}; vm.apps = {}; vm.leads = {};
  vm.loading = true;

  function load() {
    ApiClient.list('run_log').then(function (rows) {
      rows.forEach(function (r) { r.counts = RunPoller.parseCounts(r.outcome_counts) || {}; });
      vm.runs = rows.sort(function (a, b) { return b.started_at < a.started_at ? -1 : b.started_at > a.started_at ? 1 : b.id - a.id; });
    }).finally(function () { vm.loading = false; });
  }

  vm.countsText = function (run) {
    var keys = Object.keys(run.counts).filter(function (k) { return typeof run.counts[k] === 'number'; });
    if (run.run_type === 'apply') { keys = keys.filter(function (k) { return ['queued', 'processed', 'current_lead_id'].indexOf(k) === -1; }); }
    if (run.run_type === 'search') { keys = keys.filter(function (k) { return ['new_posts', 'detailed', 'promoted', 'detail_errors'].indexOf(k) !== -1; }); }
    return keys.map(function (k) { return k + ' ' + run.counts[k]; }).join(', ');
  };

  vm.trackName = function (id) { return id === null ? '' : (vm.tracks[id] || 'track ' + id); };

  vm.toggle = function (run) {
    vm.expanded[run.id] = !vm.expanded[run.id];
    if (vm.expanded[run.id] && run.run_type === 'apply' && !vm.apps[run.id]) {
      ApiClient.list('application', { run_id: run.id }).then(function (apps) { vm.apps[run.id] = apps; });
    }
  };

  vm.leadTitle = function (id) { return vm.leads[id] ? vm.leads[id].position_title : 'lead #' + id; };

  ApiClient.list('track').then(function (rows) {
    rows.forEach(function (t) { vm.tracks[t.id] = t.role_name + ' (' + t.seniority + ')'; });
  });
  ApiClient.list('lead').then(function (rows) { rows.forEach(function (l) { vm.leads[l.id] = l; }); });
  vm.refresh = load;
  load();
}]);
