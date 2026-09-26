// manual-post-modal (10.EL.20, page 4). Same shape as offer-modal.directive.js: restrict 'E',
// isolate scope, link binds dialog state/api directly. Embedded in posts.html itself (not
// index.html) since, unlike OfferDialog, ManualPostDialog is only ever opened from the Posts
// page.
angular.module('easymcfApp').directive('manualPostModal', ['ManualPostDialog', function (ManualPostDialog) {
  return {
    restrict: 'E',
    scope: {},
    link: function (scope) { scope.dialog = ManualPostDialog.state; scope.api = ManualPostDialog; },
    template:
      '<div class="modal" ng-if="dialog.open" data-testid="manual-post-dialog"><h2>Add a posting manually</h2>' +
      '<form ng-submit="api.save()">' +
      '<label>Track <select required ng-model="dialog.trackId" ' +
      'ng-options="t.id as (t.role_name + \' / \' + t.seniority) for t in dialog.tracks" ' +
      'data-testid="manual-post-track-select"></select></label>' +
      '<label>Title <input required ng-model="dialog.positionTitle" data-testid="manual-post-title"></label>' +
      '<label>Company <input required ng-model="dialog.companyName" data-testid="manual-post-company"></label>' +
      '<label>Post URL <input type="url" ng-model="dialog.urlRef" data-testid="manual-post-url"></label>' +
      '<label>Salary (SGD) <input type="number" min="0" ng-model="dialog.salaryHigh" data-testid="manual-post-salary"></label>' +
      '<label>Posted date <input type="date" required ng-model="dialog.postedDate" data-testid="manual-post-posted-date"></label>' +
      '<span ng-if="dialog.error" data-testid="manual-post-error">{{dialog.error.message}}</span>' +
      '<div><button type="submit" data-testid="manual-post-save">Save posting</button>' +
      '<button type="button" class="secondary" ng-click="api.cancel()" data-testid="manual-post-cancel">Cancel</button></div>' +
      '</form></div>'
  };
}]);
