angular.module('easymcfApp').controller('TracksCtrl', ['$location', 'ApiClient', 'ErrorService', function ($location, ApiClient, ErrorService) {
  var vm = this;
  vm.tracks = []; vm.roles = []; vm.cvs = []; vm.profiles = {};
  vm.showArchived = false; vm.form = {}; vm.fieldError = null; vm.searchProfileTrack = null;

  function load() {
    ApiClient.list('track').then(function (rows) { vm.tracks = rows; });
    ApiClient.list('role').then(function (rows) { vm.roles = rows; });
    ApiClient.list('cv').then(function (rows) { vm.cvs = rows.filter(function (c) { return c.is_active; }); });  // 11.IS.19
    ApiClient.list('search_profile').then(function (rows) {
      vm.profiles = {};
      rows.forEach(function (p) { vm.profiles[p.track_id] = p; });
    });
  }

  vm.visible = function () {
    return vm.tracks.filter(function (t) { return vm.showArchived || t.is_active; });
  };
  vm.edit = function (track) { vm.form = angular.copy(track); };
  vm.save = function () {
    var body = { role_id: vm.form.role_id, seniority: vm.form.seniority, default_cv_id: vm.form.default_cv_id || null };
    var request = vm.form.id ? ApiClient.update('track', vm.form.id, body) : ApiClient.create('track', body);
    request.then(function () { vm.form = {}; vm.fieldError = null; load(); },
                 function (r) { vm.fieldError = ErrorService.fieldMessage(r); });
  };
  vm.setActive = function (track, active) { ApiClient.update('track', track.id, { is_active: active }).then(load); };
  vm.configureSearch = function (track) { $location.path('/tracks/' + track.id + '/search'); };
  vm.manageCvs = function () { $location.path('/cvs'); };

  load();
}]);
