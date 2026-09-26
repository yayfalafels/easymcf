angular.module('easymcfApp').directive('confirmModal', ['ConfirmDialog', function (ConfirmDialog) {
  return {
    restrict: 'E',
    scope: {},
    link: function (scope) { scope.dialog = ConfirmDialog.state; scope.answer = ConfirmDialog.answer; },
    template:
      '<div class="modal" ng-if="dialog.open" data-testid="confirm-modal">' +
      '<p data-testid="confirm-message">{{dialog.message}}</p>' +
      '<button data-testid="confirm-yes" ng-click="answer(true)">{{dialog.confirmLabel}}</button>' +
      '<button data-testid="confirm-no" ng-click="answer(false)">Cancel</button></div>'
  };
}]);
