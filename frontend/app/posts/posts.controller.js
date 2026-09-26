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

    // Search progress display (10.IS.16): four lights in two pairs, driven by the `stage`
    // key search.py merges into run_log.outcome_counts. Each running stage lights a pair,
    // since pages are fetched and their posts saved in the same step, and each post is
    // promoted as soon as its details load. Earlier pairs are green, the current pair
    // yellow (red if the run failed there), later ones grey.
    var STAGES = [
      { key: 'searching', text: 'searching for posts' },
      { key: 'detailing', text: 'reading post details' }
    ];
    var PAIR_OF_STEP = [0, 0, 1, 1];

    function stageIndex() {
      var counts = vm.runner.outcomeCounts || {};
      if (counts.stage === 'done') { return STAGES.length; }
      for (var i = 0; i < STAGES.length; i++) { if (STAGES[i].key === counts.stage) { return i; } }
      return vm.runner.active ? 0 : -1;  // no progress written yet: running → first stage, idle → none
    }

    vm.statusText = function () {
      var index = stageIndex();
      return vm.runner.active && index >= 0 && index < STAGES.length ? STAGES[index].text + '...' : '';
    };

    vm.lightClass = function (step) {
      var index = stageIndex(), pair = PAIR_OF_STEP[step];
      if (index < 0 || pair > index) { return 'light-grey'; }
      if (pair < index) { return 'light-green'; }
      return vm.runner.status === 'failed' ? 'light-red' : 'light-yellow';
    };

    // Fixed step list, with primitive-returning getters: an ng-repeat over a function that
    // builds fresh objects each digest never stabilises (infdig).
    vm.steps = ['pages', 'posts found', 'loaded', 'promoted'];

    vm.stepValue = function (step) {
      var c = vm.runner.outcomeCounts || {};
      return [c.pages || 0, c.cards || 0, (c.detailed || 0) + (c.closed || 0), c.promoted || 0][step];
    };

    vm.stepDetail = function (step) {
      var c = vm.runner.outcomeCounts || {};
      if (step === 0) { return c.keywords_total ? 'keyword ' + (c.keywords || 0) + ' of ' + c.keywords_total : ''; }
      if (step === 1) { return c.cards ? (c.new_posts || 0) + ' new' : ''; }
      if (step === 2) { return c.detail_total !== undefined ? 'of ' + c.detail_total : ''; }
      return vm.runner.active && c.stage === 'detailing' ? 'so far' : '';
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
