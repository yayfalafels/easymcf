// FE-AUTH-01/02 — the signed-in user lives in memory only. The session itself is the HttpOnly cookie.
angular.module('easymcfApp').factory('AuthService', ['$q', '$location', 'ApiClient', function ($q, $location, ApiClient) {
  var state = { user: null, config: { google_enabled: false } };
  var ready = $q.all([
    ApiClient.authConfig().then(function (c) { state.config = c; }, angular.noop),
    ApiClient.me().then(function (u) { state.user = u; }, function () { state.user = null; })
  ]);

  function set(user) { state.user = user; return user; }

  return {
    state: state,
    ready: ready,
    require: function () {
      return ready.then(function () { return state.user ? state.user : $q.reject('unauthenticated'); });
    },
    redirectIfSignedIn: function () {
      return ready.then(function () { if (state.user) { $location.path('/leads'); } });
    },
    signin: function (body) { return ApiClient.signin(body).then(set); },
    signup: function (body) { return ApiClient.signup(body).then(set); },
    signout: function () {
      return ApiClient.signout().then(function () { state.user = null; $location.path('/signin'); });
    },
    uploadPhoto: function (file) { return ApiClient.uploadPhoto(state.user.id, file).then(set); },
    removePhoto: function () { return ApiClient.removePhoto(state.user.id).then(set); },
    initials: function () {
      var user = state.user;
      if (!user) { return ''; }
      var words = (user.name || '').trim().split(/\s+/).filter(Boolean);
      return words.length ? words.slice(0, 2).map(function (w) { return w[0].toUpperCase(); }).join('') : user.email[0].toUpperCase();
    }
  };
}]);
