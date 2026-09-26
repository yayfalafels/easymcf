angular.module('easymcfApp').controller('CvsCtrl', ['$location', 'ApiClient', 'ErrorService', function ($location, ApiClient, ErrorService) {
  var vm = this;
  vm.cvs = []; vm.form = {}; vm.fieldError = null;
  // A removed label that history still uses is retired, not deleted (11.IS.19); the page lists active labels.
  function load() { ApiClient.list('cv').then(function (rows) { vm.cvs = rows.filter(function (c) { return c.is_active; }); }); }
  vm.edit = function (cv) { vm.form = angular.copy(cv); };
  vm.save = function () {
    var request = vm.form.id ? ApiClient.update('cv', vm.form.id, { label: vm.form.label }) : ApiClient.create('cv', { label: vm.form.label });
    request.then(function () { vm.form = {}; vm.fieldError = null; load(); }, function (response) { vm.fieldError = ErrorService.fieldMessage(response); });
  };
  vm.remove = function (cv) { ApiClient.remove('cv', cv.id).then(load, function (response) { vm.fieldError = ErrorService.fieldMessage(response); }); };
  // Reached from Tracks' "Manage CVs" and from the Applications CV override (11.CK.10); back returns there.
  vm.fromApplications = $location.search().from === 'applications';
  vm.back = function () { $location.url(vm.fromApplications ? '/applications' : '/tracks'); };
  load();
}]);