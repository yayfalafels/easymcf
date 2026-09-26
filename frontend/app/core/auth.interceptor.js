// FE-AUTH-03 — a 401 from any call except the sign-in forms and the startup check ends the session client-side.
angular.module('easymcfApp').factory('AuthInterceptor', ['$q', '$location', '$injector', function ($q, $location, $injector) {
  return {
    responseError: function (r) {
      var exempt = /\/auth\/(signin|signup|me)$/.test(r.config.url);
      if (r.status === 401 && !exempt) {
        $injector.get('AuthService').state.user = null;
        var next = $location.path();   // read before the path changes, since path('/signin') runs first in a chain
        if (next !== '/signin' && next !== '/signup') { $location.path('/signin').search({ next: next }); }
      }
      return $q.reject(r);
    }
  };
}]);
