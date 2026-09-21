// FE-RTE-01/03 — HTML5-mode routing. Every route except /signin and /signup is guarded: it resolves only for a
// signed-in user, and otherwise the user goes to /signin and returns to the requested page afterward.
angular.module('easymcfApp').config(['$routeProvider', '$locationProvider', '$httpProvider',
  function ($routeProvider, $locationProvider, $httpProvider) {
    $locationProvider.html5Mode(true);
    $httpProvider.interceptors.push('AuthInterceptor');

    var guarded = { auth: ['AuthService', function (a) { return a.require(); }] };
    var anonymous = { anon: ['AuthService', function (a) { return a.redirectIfSignedIn(); }] };

    $routeProvider
      .when('/', { redirectTo: '/leads' })
      .when('/signin', { templateUrl: 'app/auth/signin.html', controller: 'AuthCtrl', controllerAs: 'vm', resolve: anonymous })
      .when('/signup', { templateUrl: 'app/auth/signup.html', controller: 'AuthCtrl', controllerAs: 'vm', resolve: anonymous })
      .when('/tracks', { templateUrl: 'app/tracks/tracks.html', controller: 'TracksCtrl', controllerAs: 'vm', resolve: guarded })
      .when('/tracks/:trackId/search', { templateUrl: 'app/tracks/search-profile.html', controller: 'SearchProfileCtrl', controllerAs: 'vm', resolve: guarded })
      .when('/cvs', { templateUrl: 'app/cvs/cvs.html', controller: 'CvsCtrl', controllerAs: 'vm', resolve: guarded })
      .when('/leads', { templateUrl: 'app/leads/leads.html', controller: 'LeadsCtrl', controllerAs: 'vm', resolve: guarded })
      .when('/offers', { templateUrl: 'app/offers/offers.html', controller: 'OffersCtrl', controllerAs: 'vm', resolve: guarded })
      .otherwise({ redirectTo: '/leads' });
  }
]).run(['$rootScope', '$location', function ($rootScope, $location) {
  $rootScope.$on('$routeChangeError', function (event, current, previous, rejection) {
    if (rejection === 'unauthenticated') {
      var next = $location.path();   // read before the path changes, since path('/signin') runs first in a chain
      $location.path('/signin').search({ next: next });
    }
  });
}]);
