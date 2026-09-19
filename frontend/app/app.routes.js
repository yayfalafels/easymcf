// FE-RTE-01 — HTML5-mode routing. `/` stays on env-status; each screen adds its own
// route as it lands (milestones 09-11 add Tracks, Leads, and later screens).
angular.module('easymcfApp').config(['$routeProvider', '$locationProvider',
  function ($routeProvider, $locationProvider) {
    $locationProvider.html5Mode(true);

    $routeProvider
      .when('/', { templateUrl: 'app/env-status/env-status.html', controller: 'EnvStatusCtrl' })
      .when('/tracks', { templateUrl: 'app/tracks/tracks.html', controller: 'TracksCtrl', controllerAs: 'vm' })
      .when('/tracks/:trackId/search', { templateUrl: 'app/tracks/search-profile.html', controller: 'SearchProfileCtrl', controllerAs: 'vm' })
      .when('/cvs', { templateUrl: 'app/cvs/cvs.html', controller: 'CvsCtrl', controllerAs: 'vm' })
      .when('/leads', { templateUrl: 'app/leads/leads.html', controller: 'LeadsCtrl', controllerAs: 'vm' })
      .otherwise({ redirectTo: '/' });
  }
]);
