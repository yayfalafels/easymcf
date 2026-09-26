// ApplicationsCtrl (11.EL.16, page 7). The apply queue is the signed-in user's open TOAPPLY leads, read with
// the effective CV and latest attempt the lead resource resolves server-side (the same rule the run uses), plus
// a per-row CV override, drop behind the confirmation modal, the inline session gate, the async run through
// RunPoller's apply channel, and the results view with Workflow 7's next action per outcome.
angular.module('easymcfApp').controller('ApplicationsCtrl', ['ApiClient', 'RunPoller', 'ConfirmDialog', 'McfConnect',
  function (ApiClient, RunPoller, ConfirmDialog, McfConnect) {
    var vm = this;
    vm.loading = true;
    vm.queue = []; vm.cvs = []; vm.tracks = {};
    vm.results = null; vm.resultRun = null;
    vm.runner = RunPoller.stateFor('apply');
    vm.session = McfConnect.state;
    McfConnect.ensurePolling();

    vm.OUTCOMES = {
      applied: 'Moved to APPLIED. Follow it up on the Leads page.',
      questionnaire_required: 'Complete the questionnaire on MCF, then mark the lead APPLIED from Lead Detail.',
      cv_selector_error: 'The resume picker did not load as expected. It is retried next run, or apply on MCF.',
      unable_to_apply: 'The apply button never became available. It is retried next run, or apply on MCF.',
      post_unavailable: 'Closed as apply_failed: the posting could not be loaded.',
      cv_not_found: 'No MCF resume matches this CV label. Choose another CV, or rename the label.',
      post_closed: 'Closed as apply_failed: the posting is closed.',
      invalid_input: 'The lead is missing a field the run needs. Fix it, then run again.'
    };

    function loadQueue() {
      return ApiClient.list('lead', { stage: 'TOAPPLY' }).then(function (rows) {
        vm.queue = rows.filter(function (r) { return r.status === 'OPEN'; });
        vm.queue.forEach(function (r) { r.cvChoice = r.cv_id === null ? '' : String(r.cv_id); });
      }).finally(function () { vm.loading = false; });
    }

    function loadResults(run) {
      vm.resultRun = run;
      vm.resultCounts = RunPoller.parseCounts(run.outcome_counts) || {};
      ApiClient.list('application', { run_id: run.id }).then(function (apps) {
        return ApiClient.list('lead').then(function (leads) {
          var byId = {};
          leads.forEach(function (l) { byId[l.id] = l; });
          vm.results = apps.map(function (a) { return angular.extend({ lead: byId[a.lead_id] || {} }, a); });
        });
      });
    }

    vm.sessionValid = function () { return McfConnect.hasValidSession(); };
    vm.sessionStatus = function () { return vm.session.session ? vm.session.session.status : 'missing'; };
    vm.connect = function () { McfConnect.openPopup(); };
    vm.runnable = function () { return vm.queue.filter(function (r) { return !r.apply_blocked; }); };
    vm.cvLabel = function (id) {
      var cv = vm.cvs.filter(function (c) { return c.id === id; })[0];
      return cv ? cv.label : '';
    };
    vm.trackName = function (id) { return vm.tracks[id] || ''; };

    vm.runDisabledReason = function () {
      if (vm.runner.active) { return 'An apply run is in progress.'; }
      if (!vm.sessionValid()) { return 'Connect your MCF session first: the run needs a signed-in MCF session.'; }
      if (!vm.runnable().length) { return vm.queue.length ? 'Every queued lead is blocked on a missing CV.' : 'The queue is empty.'; }
      return '';
    };

    vm.overrideCv = function (lead) {
      var cvId = lead.cvChoice === '' ? null : Number(lead.cvChoice);
      ApiClient.update('lead', lead.id, { cv_id: cvId }).then(loadQueue, loadQueue);
    };

    vm.drop = function (lead) {
      ConfirmDialog.ask({ message: 'Drop "' + lead.position_title + '" from the apply queue? The lead closes as dropped.',
                          confirmLabel: 'Drop lead' })
        .then(function () {
          return ApiClient.update('lead', lead.id, { stage: 'CLOSED', close_reason: 'dropped' }).then(loadQueue);
        }, angular.noop);
    };

    function follow(runId) {
      vm.results = null;
      return RunPoller.start(runId, 'apply').then(function (run) { loadResults(run); loadQueue(); });
    }

    vm.run = function () {
      var n = vm.runnable().length;
      ConfirmDialog.ask({ message: 'Apply to ' + n + (n === 1 ? ' posting' : ' postings') + ' on MCF with your ' +
                          vm.sessionStatus() + ' session? This submits real applications.', confirmLabel: 'Run apply batch' })
        .then(function () {
          return ApiClient.triggerApplyRun().then(function (run) { return follow(run.id); });
        }, angular.noop);
    };

    vm.progress = function () {
      var c = vm.runner.outcomeCounts || {};
      if (c.queued === undefined) { return 'Starting the apply run...'; }
      return 'Applying: ' + (c.processed || 0) + ' of ' + c.queued + ' leads done' +
        (c.current_lead_id ? ', now lead #' + c.current_lead_id : '');
    };

    vm.progressCounts = function () {
      var c = vm.runner.outcomeCounts || {};
      return Object.keys(c).filter(function (k) { return vm.OUTCOMES[k]; })
        .map(function (k) { return k + ' ' + c[k]; }).join(', ');
    };

    ApiClient.list('cv').then(function (rows) { vm.cvs = rows; });
    ApiClient.list('track').then(function (rows) {
      rows.forEach(function (t) { vm.tracks[t.id] = t.role_name + ' (' + t.seniority + ')'; });
    });
    loadQueue();
    // Resume an apply run already in flight, after navigation or a reload.
    if (!vm.runner.active) {
      ApiClient.list('run_log', { run_type: 'apply', status: 'running' }).then(function (rows) {
        if (rows.length) { follow(rows[rows.length - 1].id); }
      });
    } else {
      RunPoller.start(vm.runner.runId, 'apply').then(function (run) { loadResults(run); loadQueue(); });
    }
  }
]);
