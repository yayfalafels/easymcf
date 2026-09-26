// FE-AUTH-04 — the signed-in user section: the photo (or initials) in a circle, with Upload photo, Remove photo, and Log out.
angular.module('easymcfApp').directive('userMenu', ['AuthService', function (AuthService) {
  return {
    restrict: 'E',
    scope: {},
    link: function (scope, element) {
      scope.auth = AuthService;
      scope.menu = { open: false };   // an object, since ng-if child scopes would shadow a plain boolean
      scope.error = null;
      scope.pick = function () { element[0].querySelector('[data-testid="user-menu-photo-input"]').click(); };
      element.on('change', function (event) {
        var input = event.target;
        if (!input.matches || !input.matches('[data-testid="user-menu-photo-input"]')) { return; }
        var file = input.files[0];
        input.value = '';
        if (!file) { return; }
        if (file.size > 2 * 1024 * 1024) { scope.$applyAsync(function () { scope.error = 'The image is larger than 2 MB.'; }); return; }
        scope.$applyAsync(function () {
          scope.error = null;
          AuthService.uploadPhoto(file).then(function () { scope.menu.open = false; }, function (r) {
            scope.error = (r.data && r.data.message) || 'The photo could not be uploaded.';
          });
        });
      });
    },
    template:
      '<div class="user-section" data-testid="user-section" ng-if="auth.state.user">' +
      '<button type="button" class="avatar" ng-click="menu.open = !menu.open" data-testid="user-avatar" aria-label="Account menu">' +
      '<img ng-if="auth.state.user.photo_url" ng-src="{{auth.state.user.photo_url}}" data-testid="user-photo" alt="">' +
      '<span ng-if="!auth.state.user.photo_url" data-testid="user-initials">{{auth.initials()}}</span></button>' +
      '<div class="user-menu" ng-if="menu.open" data-testid="user-menu">' +
      '<strong data-testid="user-name">{{auth.state.user.name}}</strong><span>{{auth.state.user.email}}</span>' +
      '<button type="button" ng-click="pick()" data-testid="user-menu-upload">Upload photo</button>' +
      '<button type="button" ng-if="auth.state.user.photo_url" ng-click="auth.removePhoto()" data-testid="user-menu-remove-photo">Remove photo</button>' +
      '<button type="button" ng-click="auth.signout()" data-testid="user-menu-logout">Log out</button>' +
      '<span class="field-error" ng-if="error" data-testid="user-menu-error">{{error}}</span></div>' +
      '<input type="file" accept="image/png,image/jpeg,image/webp" hidden data-testid="user-menu-photo-input"></div>'
  };
}]);
