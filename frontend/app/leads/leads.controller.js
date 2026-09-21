angular.module('easymcfApp').controller('LeadsCtrl', ['$timeout', 'ApiClient', 'ConfirmDialog', 'ErrorService', function ($timeout, ApiClient, ConfirmDialog, ErrorService) {
  var vm = this;
  var DAY_MS = 86400000;
  vm.tabs = [
    { key: 'toapply', label: 'TOAPPLY', stages: ['TOAPPLY'], layout: 'table', sort: 'days' },
    { key: 'applied', label: 'Applied', stages: ['APPLIED'], layout: 'table', sort: 'days' },
    { key: 'callbacks', label: 'Callbacks', stages: ['CALLBACK'], layout: 'card', sort: 'contact' },
    { key: 'interviews', label: 'Interviews', stages: ['INTERVIEW'], layout: 'card', sort: 'contact' },
    { key: 'offers', label: 'Offers', stages: ['OFFER'], layout: 'card', sort: 'contact' },
    { key: 'closed', label: 'Closed', stages: ['CLOSED'], layout: 'table', sort: 'updated' }
  ];
  vm.tab = vm.tabs[0]; vm.trackId = ''; vm.query = ''; vm.leads = []; vm.tracks = []; vm.selected = null; vm.checked = {};
  vm.adding = false; vm.manual = {}; vm.manualFieldError = null;

  function descending(get, tie) {
    return function (a, b) {
      var x = get(a), y = get(b);
      if (x === y) { return tie(a, b); }
      if (x === null || x === undefined) { return 1; }
      if (y === null || y === undefined) { return -1; }
      return x < y ? 1 : -1;
    };
  }
  var SORTS = {
    days: descending(function (l) { return vm.daysLeft(l); }, function (a, b) { return vm.title(a).localeCompare(vm.title(b)); }),
    contact: descending(function (l) { return l.last_contact_date; }, function (a, b) { return a.updated_at < b.updated_at ? 1 : -1; }),
    updated: descending(function (l) { return l.updated_at; }, function (a, b) { return a.id - b.id; })
  };

  vm.load = function () {
    vm.checked = {};
    ApiClient.list('lead').then(function (rows) { vm.leads = rows; });
    ApiClient.list('track').then(function (rows) { vm.tracks = rows; });
  };
  vm.setTab = function (tab) { vm.tab = tab; vm.checked = {}; };
  vm.inStages = function (stages, sort) {
    var rows = vm.leads.filter(function (l) {
      var query = vm.query.toLowerCase();
      var matchesQuery = !query || vm.title(l).toLowerCase().indexOf(query) !== -1 || vm.company(l).toLowerCase().indexOf(query) !== -1;
      return stages.indexOf(l.stage) !== -1 && (!vm.trackId || l.track_id === Number(vm.trackId)) && matchesQuery;
    });
    return sort ? rows.sort(SORTS[sort]) : rows;
  };
  vm.count = function (tab) { return vm.inStages(tab.stages).length; };
  vm.title = function (l) { return l.position_title; };
  vm.hasPostUrl = function (l) { return /^https?:\/\/\S+$/i.test(l.url_ref || ''); };
  vm.company = function (l) { return l.company_name; };
  vm.trackName = function (l) {
    var track = vm.tracks.filter(function (t) { return t.id === l.track_id; })[0];
    return track ? track.role_name : '';
  };
  vm.salary = function (l) { return l.stage === 'OFFER' && l.offer_amount_sgd ? l.offer_amount_sgd : l.expected_salary_sgd; };
  vm.money = function (n) { return n === null || n === undefined ? '—' : 'S$ ' + Number(n).toLocaleString('en-US'); };
  vm.excerpt = function (text) { return text && text.length > 120 ? text.slice(0, 120) + '…' : text; };
  vm.daysLeft = function (l) {
    return l.deadline ? Math.ceil((Date.parse(l.deadline) - Date.parse(new Date().toISOString().slice(0, 10))) / DAY_MS) : null;
  };
  vm.warn = function (l) { var d = vm.daysLeft(l); return d !== null && d <= 7 && l.status === 'OPEN'; };
  vm.open = function (l) {
    vm.selected = null;
    $timeout(function () { vm.selected = l; });
  };
  vm.closeDetail = function () { vm.selected = null; vm.load(); };

  vm.checkedIds = function () {
    return Object.keys(vm.checked).filter(function (id) { return vm.checked[id]; }).map(Number);
  };
  vm.checkedCount = function () { return vm.checkedIds().length; };
  vm.toggleAll = function (on) {
    vm.inStages(['TOAPPLY']).forEach(function (l) { vm.checked[l.id] = on; });
  };
  function batch(stage, extra) {
    var rows = vm.checkedIds().map(function (id) { return angular.extend({ id: id, stage: stage }, extra); });
    return ApiClient.batch('lead', rows, function (response) {
      var lead = vm.leads.filter(function (l) { return response.data && l.id === response.data.lead_id; })[0];
      return lead ? vm.title(lead) : null;
    }).then(vm.load, angular.noop);
  }
  vm.apply = function () { batch('APPLIED'); };
  vm.drop = function () {
    var n = vm.checkedCount();
    ConfirmDialog.ask({ message: 'Drop ' + n + (n === 1 ? ' lead' : ' leads') + '?', confirmLabel: 'Drop leads' })
      .then(function () { batch('CLOSED', { close_reason: 'dropped' }); }, angular.noop);
  };
  vm.settle = function (lead, status) {
    ConfirmDialog.ask({ message: 'Mark this offer ' + status + '? The lead will close.', confirmLabel: 'Mark ' + status })
      .then(function () { return ApiClient.update('offer', lead.offer_id, { status: status }); })
      .then(vm.load, angular.noop);
  };

  vm.startManual = function () {
    vm.adding = true;
    vm.manualFieldError = null;
    vm.manual = { track_id: vm.trackId ? Number(vm.trackId) : null, posted_date: new Date() };
  };
  vm.cancelManual = function () { vm.adding = false; vm.manual = {}; vm.manualFieldError = null; };
  function dateValue(value) {
    if (!value) { return null; }
    if (typeof value === 'string') { return value; }
    return value.getFullYear() + '-' + String(value.getMonth() + 1).padStart(2, '0') + '-' + String(value.getDate()).padStart(2, '0');
  }
  vm.createManual = function () {
    var manual = vm.manual;
    var lead = {
      track_id: Number(manual.track_id), position_title: manual.position_title, company_name: manual.company_name,
      url_ref: manual.url_ref || null, salary_high: manual.salary_high || null, posted_date: dateValue(manual.posted_date)
    };
    ApiClient.createManualLead(lead).then(function () {
      vm.adding = false;
      vm.manual = {};
      vm.manualFieldError = null;
      vm.tab = vm.tabs[1];
      vm.load();
    }, function (response) { vm.manualFieldError = ErrorService.fieldMessage(response); });
  };

  vm.load();
}]);
