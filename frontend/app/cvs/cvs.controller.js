angular.module('easymcfApp').controller('CvsCtrl', ['$location', 'ApiClient', 'ErrorService', function ($location, ApiClient, ErrorService) {
  var vm = this;
  vm.cvs = []; vm.form = {}; vm.fieldError = null;
  function load() { ApiClient.list('cv').then(function (rows) { vm.cvs = rows; }); }
  vm.edit = function (cv) { vm.form = angular.copy(cv); };
  vm.save = function () {
    var request = vm.form.id ? ApiClient.update('cv', vm.form.id, { label: vm.form.label }) : ApiClient.create('cv', { label: vm.form.label });
    request.then(function () { vm.form = {}; vm.fieldError = null; load(); }, function (response) { vm.fieldError = ErrorService.fieldMessage(response); });
  };
  vm.remove = function (cv) { ApiClient.remove('cv', cv.id).then(load, function (response) { vm.fieldError = ErrorService.fieldMessage(response); }); };
  vm.back = function () { $location.path('/tracks'); };
  load();
}]);