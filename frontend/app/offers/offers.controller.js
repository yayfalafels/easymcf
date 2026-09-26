angular.module('easymcfApp').controller('OffersCtrl', ['ApiClient', 'ConfirmDialog', 'OfferDialog', function (ApiClient, ConfirmDialog, OfferDialog) {
  var vm = this;
  vm.offers = []; vm.status = '';
  vm.statuses = ['open', 'accepted', 'rejected', 'withdrawn', 'expired'];

  vm.load = function () {
    ApiClient.list('offer', vm.status ? { status: vm.status } : {}).then(function (rows) {
      vm.offers = rows.sort(function (a, b) {
        return a.offer_date === b.offer_date ? b.id - a.id : (a.offer_date < b.offer_date ? 1 : -1);
      });
    });
  };
  vm.create = function () { OfferDialog.open(null).then(vm.load, angular.noop); };
  vm.save = function (offer) {
    ApiClient.update('offer', offer.id, { amount_sgd: Number(offer.amount_sgd), deadline: offer.deadline || null }).then(vm.load);
  };
  vm.settle = function (offer, status) {
    ConfirmDialog.ask({ message: 'Mark this offer ' + status + '? The lead will close.', confirmLabel: 'Mark ' + status })
      .then(function () { return ApiClient.update('offer', offer.id, { status: status }); })
      .then(vm.load, angular.noop);
  };

  vm.load();
}]);
