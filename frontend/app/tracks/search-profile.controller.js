angular.module('easymcfApp').controller('SearchProfileCtrl', ['$routeParams', '$location', 'ApiClient', 'ErrorService',
  function ($routeParams, $location, ApiClient, ErrorService) {
    var vm = this;
    vm.trackId = Number($routeParams.trackId); vm.profile = null; vm.schedule = null; vm.fieldError = null;

    function load() {
      ApiClient.get('track', vm.trackId).then(function (track) { vm.track = track; });
      ApiClient.get('search_profile', vm.trackId).then(function (profile) { vm.profile = profile; });
      ApiClient.get('search_schedule', vm.trackId).then(function (schedule) { vm.schedule = schedule; });
    }

    vm.save = function () {
      var profile = {
        keywords: vm.profile.keywords, min_salary: vm.profile.min_salary, max_age_weeks: vm.profile.max_age_weeks,
        min_match_score: vm.profile.min_match_score, employment_type: vm.profile.employment_type
      };
      var schedule = {
        schedule_enabled: vm.schedule.schedule_enabled, schedule_interval_hours: vm.schedule.schedule_interval_hours,
        next_run_at: vm.schedule.next_run_at
      };
      ApiClient.update('search_profile', vm.trackId, profile).then(function () {
        return ApiClient.update('search_schedule', vm.trackId, schedule);
      }).then(function () { vm.fieldError = null; load(); }, function (response) { vm.fieldError = ErrorService.fieldMessage(response); });
    };
    vm.back = function () { $location.path('/tracks'); };
    load();
  }]);