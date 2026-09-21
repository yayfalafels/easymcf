angular.module('easymcfApp').directive('offerModal', ['OfferDialog', function (OfferDialog) {
  return {
    restrict: 'E',
    scope: {},
    link: function (scope) { scope.dialog = OfferDialog.state; scope.api = OfferDialog; },
    template:
      '<div class="modal" ng-if="dialog.open" data-testid="offer-dialog"><h2>Attach an offer</h2>' +
      '<label>Search leads <input ng-model="dialog.search" data-testid="offer-lead-search"></label>' +
      '<label>Lead <select ng-model="dialog.leadId" ng-change="api.choose()" ng-options="l.id as api.label(l) for l in api.matches()" data-testid="offer-lead"></select></label>' +
      '<label>Offer date <input type="date" ng-model="dialog.offerDate" data-testid="offer-date"></label>' +
      '<label>Amount (SGD) <input type="number" min="1" ng-model="dialog.amount" data-testid="offer-amount"></label>' +
      '<label>Deadline <input type="date" ng-model="dialog.deadline" data-testid="offer-deadline"></label>' +
      '<span ng-if="dialog.error" data-testid="offer-error">{{dialog.error.message}}</span>' +
      '<div><button ng-click="api.save()" data-testid="offer-save">Save offer</button>' +
      '<button class="secondary" ng-click="api.cancel()" data-testid="offer-cancel">Cancel</button></div></div>'
  };
}]);
