// FE-AUTH-05 — one controller serves the Sign in and Sign up pages.
angular.module('easymcfApp').controller('AuthCtrl', ['$location', 'AuthService', 'ErrorService', function ($location, AuthService, ErrorService) {
  var vm = this;
  var search = $location.search();
  var MESSAGES = {
    google_denied: 'Google sign-in was cancelled.',
    google_invalid: 'Google sign-in could not be verified. Try again.',
    google_unavailable: 'Google could not be reached. Try again later.',
    google_email_unverified: 'The Google account email is not verified.'
  };
  vm.rules = [
    ['too_short', 'At least 12 characters'], ['no_lowercase', 'A lowercase letter'], ['no_uppercase', 'An uppercase letter'],
    ['no_digit', 'A digit'], ['no_symbol', 'A symbol'], ['contains_identity', 'Does not contain your email or name']
  ];
  vm.form = {};
  vm.error = MESSAGES[search.error] || null;
  vm.fieldError = null;
  vm.serverRules = [];
  vm.config = AuthService.state.config;
  vm.next = search.next && /^\/(?!\/)/.test(search.next) ? search.next : '/leads';
  vm.googleUrl = '/api/v1/auth/google/start?next=' + encodeURIComponent(vm.next);

  // The live checklist mirrors the server rules for feedback only. The server response stays authoritative.
  vm.unmet = function (code) {
    var password = vm.form.password || '';
    var lowered = password.toLowerCase();
    var local = (vm.form.email || '').split('@')[0].toLowerCase();
    var name = (vm.form.name || '').replace(/\s+/g, '').toLowerCase();
    return {
      too_short: password.length < 12,
      no_lowercase: !/[a-z]/.test(password),
      no_uppercase: !/[A-Z]/.test(password),
      no_digit: !/\d/.test(password),
      no_symbol: !/[^\p{L}\p{N}\s]/u.test(password),
      contains_identity: (local.length >= 4 && lowered.indexOf(local) !== -1) || (name.length >= 4 && lowered.indexOf(name) !== -1)
    }[code];
  };
  vm.state = function (code) { return vm.unmet(code) || vm.serverRules.indexOf(code) !== -1 ? 'unmet' : 'met'; };

  function done() { $location.search({}).path(vm.next); }
  function failed(response) {
    vm.fieldError = ErrorService.fieldMessage(response);
    vm.serverRules = (response.data && response.data.rules) || [];
    vm.error = response.status === 401 || response.status === 429 ? response.data.message : null;
  }
  vm.signin = function () {
    vm.error = null; vm.fieldError = null;
    AuthService.signin({ email: vm.form.email || '', password: vm.form.password || '' }).then(done, failed);
  };
  vm.signup = function () {
    vm.error = null; vm.fieldError = null; vm.serverRules = [];
    AuthService.signup({ name: vm.form.name || '', email: vm.form.email || '', password: vm.form.password || '' }).then(done, failed);
  };
}]);
