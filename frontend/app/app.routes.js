// FE-RTE-01 — HTML5-mode routing. `/` and any unmatched path redirect to `/leads`, the
// landing page; each screen adds its own route as it lands.
angular.module('easymcfApp').config(['$routeProvider', '$locationProvider',
  function ($routeProvider, $locationProvider) {
    $locationProvider.html5Mode(true);

    $routeProvider
      .when('/', { redirectTo: '/leads' })
      .when('/tracks', { templateUrl: 'app/tracks/tracks.html', controller: 'TracksCtrl', controllerAs: 'vm' })
      .when('/tracks/:trackId/search', { templateUrl: 'app/tracks/search-profile.html', controller: 'SearchProfileCtrl', controllerAs: 'vm' })
      .when('/cvs', { templateUrl: 'app/cvs/cvs.html', controller: 'CvsCtrl', controllerAs: 'vm' })
      .when('/leads', { templateUrl: 'app/leads/leads.html', controller: 'LeadsCtrl', controllerAs: 'vm' })
      .otherwise({ redirectTo: '/leads' });
  }
]);
