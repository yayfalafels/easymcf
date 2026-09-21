angular.module('easymcfApp').controller('LeadDetailCtrl', ['$scope', '$q', 'ApiClient', 'ConfirmDialog', 'OfferDialog', 'ErrorService',
  function ($scope, $q, ApiClient, ConfirmDialog, OfferDialog, ErrorService) {
    var d = this;
    var NEXT = { TOAPPLY: 'APPLIED', APPLIED: 'CALLBACK', CALLBACK: 'INTERVIEW', INTERVIEW: 'OFFER' };
    var EDITABLE = ['position_title', 'company_name', 'url_ref', 'deadline', 'applied_date', 'first_attempt_date', 'expected_salary_sgd', 'track_id'];
    d.lead = angular.copy($scope.vm.selected);
    d.loaded = angular.copy(d.lead);
    d.reasons = ['offer_accepted', 'rejected', 'withdrawn', 'expired', 'cancelled', 'duplicate', 'apply_failed', 'dropped'];
    d.closeReason = ''; d.noteText = ''; d.contactDate = new Date(); d.fieldError = null; d.activity = []; d.notes = [];

    function adopt(server) {
      var dirty = {};
      EDITABLE.forEach(function (f) {
        if ((d.lead[f] || null) !== (d.loaded[f] || null)) { dirty[f] = d.lead[f]; }
      });
      d.loaded = angular.copy(server);
      d.lead = angular.extend(angular.copy(server), dirty);
    }

    function reload() {
      ApiClient.get('lead', d.lead.id).then(adopt);
      ApiClient.list('lead_note', { lead_id: d.lead.id }).then(function (rows) { d.notes = rows.reverse(); });
      $q.all([ApiClient.list('lead_event', { lead_id: d.lead.id }),
              ApiClient.list('application', { lead_id: d.lead.id })]).then(function (r) {
        var events = r[0].map(function (e) {
          return { at: e.occurred_at, kind: e.event_type, text: e.detail, stageFrom: e.stage_from, stageTo: e.stage_to };
        });
        var attempts = r[1].map(function (a) { return { at: a.attempted_at, kind: 'application', text: a.status }; });
        d.activity = events.concat(attempts).sort(function (a, b) { return a.at < b.at ? 1 : -1; });
      });
    }
    function changed() {
      reload();
      $scope.vm.load();
    }
    d.stageLabel = function (a) {
      if (a.stageFrom === a.stageTo) { return 'at ' + a.stageTo; }
      return (a.stageFrom || 'new') + ' → ' + a.stageTo;
    };
    function save(body) {
      return ApiClient.update('lead', d.lead.id, body).then(
        function (server) {
          d.fieldError = null;
          if (server.status === 'CLOSED') { $scope.vm.closeDetail(); return; }
          changed();
        },
        function (r) { d.fieldError = ErrorService.fieldMessage(r); });
    }

    function dateValue(value) {
      if (!value) { return null; }
      if (typeof value === 'string') { return value; }
      return value.getFullYear() + '-' + String(value.getMonth() + 1).padStart(2, '0') + '-' + String(value.getDate()).padStart(2, '0');
    }

    d.hasPostUrl = function () { return /^https?:\/\/\S+$/i.test(d.lead.url_ref || ''); };

    d.nextStage = function () { return NEXT[d.lead.stage]; };
    d.advance = function () {
      if (d.lead.stage === 'INTERVIEW') {
        OfferDialog.open(d.lead).then(changed, angular.noop);
        return;
      }
      save({ stage: d.nextStage() });
    };
    d.settle = function (status) {
      ConfirmDialog.ask({ message: 'Mark this offer ' + status + '? The lead will close.', confirmLabel: 'Mark ' + status })
        .then(function () { return ApiClient.update('offer', d.lead.offer_id, { status: status }); })
        .then(function () { $scope.vm.closeDetail(); }, angular.noop);
    };
    d.tracks = function () {
      return $scope.vm.tracks.filter(function (t) { return t.is_active || t.id === d.lead.track_id; });
    };
    d.canReopen = function () { return d.lead.status === 'CLOSED' && d.lead.closed_from === 'OFFER'; };
    d.reopen = function () { save({ stage: 'INTERVIEW' }); };
    d.close = function () {
      ConfirmDialog.ask({ message: 'Close this lead?', confirmLabel: 'Close lead' })
        .then(function () { save({ stage: 'CLOSED', close_reason: d.closeReason || null }); }, angular.noop);
    };
    d.logContact = function () { save({ last_contact_date: dateValue(d.contactDate) }); };
    d.saveFields = function () {
      save({ position_title: d.lead.position_title, company_name: d.lead.company_name, url_ref: d.lead.url_ref || null,
             deadline: d.lead.deadline || null, applied_date: d.lead.applied_date || null,
             first_attempt_date: d.lead.first_attempt_date || null,
             expected_salary_sgd: d.lead.expected_salary_sgd === undefined ? null : d.lead.expected_salary_sgd,
             track_id: d.lead.track_id });
    };
    d.addNote = function () {
      ApiClient.create('lead_note', { lead_id: d.lead.id, note: d.noteText }).then(function () { d.noteText = ''; changed(); });
    };

    reload();
  }]);
