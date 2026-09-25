// PostsCtrl (10.EL.21, page 3). Track selector + "Run search" async run/poll state (RunPoller,
// FE-RUN-01..03) + age filter + results table with manual/already-a-lead tags + the Manual
// Post Entry dialog trigger. The page offers no promote control — every result this milestone
// writes promotes on its own (Scope: "unconditional system promotion").
angular.module('easymcfApp').controller('PostsCtrl', ['ApiClient', 'RunPoller', 'ManualPostDialog',
  function (ApiClient, RunPoller, ManualPostDialog) {
    var vm = this;
    vm.tracks = [];
    // A plain <option value="{{t.id}}"> (posts.html) is compared by ngModel as a literal string
    // against a plain HTML select's option values, never coerced to a number the way ng-options
    // would — so vm.trackId is kept a string here and cast with Number() at each call site,
    // the same convention leads.controller.js's own track filter already uses.
    vm.trackId = '';
    vm.maxAgeWeeks = null;
    vm.results = [];
    vm.runner = RunPoller.state;

    function loadTracks() {
      return ApiClient.list('track').then(function (rows) {
        vm.tracks = rows.filter(function (t) { return t.is_active; });
        if (!vm.trackId && vm.tracks.length) { vm.trackId = String(vm.tracks[0].id); }
      });
    }

    vm.load = function () {
      if (!vm.trackId) { vm.results = []; return; }
      var params = { track_id: Number(vm.trackId) };
      if (vm.maxAgeWeeks) { params.max_age_weeks = vm.maxAgeWeeks; }
      ApiClient.list('post', params).then(function (rows) { vm.results = rows; });
    };

    vm.runSearch = function () {
      ApiClient.triggerSearchRun(Number(vm.trackId)).then(function (run) {
        return RunPoller.start(run.id);
      }).then(vm.load);
    };

    vm.statusText = function () {
      var counts = vm.runner.outcomeCounts || {};
      return (counts.cards || 0) + ' postings found, page ' + (counts.pages || 0);
    };

    vm.addManual = function () {
      ManualPostDialog.open(vm.tracks).then(vm.load, angular.noop);
    };

    vm.age = function (row) {
      return row.posted_date ? Math.floor((Date.now() - Date.parse(row.posted_date)) / 86400000) : null;
    };

    loadTracks().then(vm.load);
  }
]);
