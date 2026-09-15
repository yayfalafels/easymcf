// FE-RTE-01 — HTML5-mode routing, one route for milestone 07.
// `/` -> env-status is a placeholder default; milestones 09-11 repoint it at
// whichever real screen becomes the landing page (ENV-SETUP-06).
angular.module('easymcfApp').config(['$routeProvider', '$locationProvider',
  function ($routeProvider, $locationProvider) {
    $locationProvider.html5Mode(true);

    $routeProvider
      .when('/', {
        templateUrl: 'app/env-status/env-status.html',
        controller: 'EnvStatusCtrl'
      })
      .otherwise({ redirectTo: '/' });
  }
]);
