angular.module('easymcfApp').controller('LeadsCtrl', ['$timeout', 'ApiClient', 'ErrorService', function ($timeout, ApiClient, ErrorService) {
  var vm = this;
  var DAY_MS = 86400000;
  vm.tabs = [
    { key: 'toapply', label: 'TOAPPLY', stages: ['TOAPPLY'] },
    { key: 'applied', label: 'Applied', stages: ['APPLIED'] },
    { key: 'callbacks', label: 'Callbacks', stages: ['CALLBACK'] },
    { key: 'interviews', label: 'Interviews', stages: ['INTERVIEW'] },
    { key: 'offers', label: 'Offers', stages: ['OFFER'] },
    { key: 'closed', label: 'Closed', stages: ['CLOSED'] }
  ];
  vm.tab = vm.tabs[0]; vm.trackId = ''; vm.query = ''; vm.leads = []; vm.tracks = []; vm.selected = null;
  vm.adding = false; vm.manual = {}; vm.manualFieldError = null;

  vm.load = function () {
    ApiClient.list('lead').then(function (rows) { vm.leads = rows; });
    ApiClient.list('track').then(function (rows) { vm.tracks = rows; });
  };
  vm.inStages = function (stages) {
    return vm.leads.filter(function (l) {
      var query = vm.query.toLowerCase();
      var matchesQuery = !query || vm.title(l).toLowerCase().indexOf(query) !== -1 || vm.company(l).toLowerCase().indexOf(query) !== -1;
      return stages.indexOf(l.stage) !== -1 && (!vm.trackId || l.track_id === Number(vm.trackId)) && matchesQuery;
    });
  };
  vm.count = function (tab) { return vm.inStages(tab.stages).length; };
  vm.title = function (l) { return l.title_override || l.position_title; };
  vm.hasPostUrl = function (l) { return /^https?:\/\/\S+$/i.test(l.url_ref || ''); };
  vm.company = function (l) { return l.company_override || l.company_name; };
  vm.daysLeft = function (l) {
    return l.deadline ? Math.ceil((Date.parse(l.deadline) - Date.parse(new Date().toISOString().slice(0, 10))) / DAY_MS) : null;
  };
  vm.warn = function (l) { var d = vm.daysLeft(l); return d !== null && d <= 7 && l.status === 'OPEN'; };
  vm.open = function (l) {
    vm.selected = null;
    $timeout(function () { vm.selected = l; });
  };
  vm.closeDetail = function () { vm.selected = null; vm.load(); };
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
      vm.tab = vm.tabs[0];
      vm.load();
    }, function (response) { vm.manualFieldError = ErrorService.fieldMessage(response); });
  };

  vm.load();
}]);
