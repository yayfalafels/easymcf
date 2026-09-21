angular.module('easymcfApp').factory('ApiClient', ['$http', '$q', 'ErrorService', function ($http, $q, ErrorService) {
  var base = '/api/v1/';

  function call(config, describe) {
    return $http(config).then(
      function (response) { return response.data; },
      function (response) { ErrorService.report(response, describe && describe(response)); return $q.reject(response); }
    );
  }

  return {
    get: function (table, id) { return call({ method: 'GET', url: base + table + '/' + id }); },
    list: function (table, params) { return call({ method: 'GET', url: base + table + '/search', params: params }); },
    create: function (table, body) { return call({ method: 'POST', url: base + table, data: body }); },
    createManualLead: function (body) { return call({ method: 'POST', url: base + 'lead/manual', data: body }); },
    batch: function (table, rows, describe) { return call({ method: 'POST', url: base + table + '/batch', data: { rows: rows } }, describe); },
    update: function (table, id, body) { return call({ method: 'PUT', url: base + table + '/' + id, data: body }); },
    remove: function (table, id) { return call({ method: 'DELETE', url: base + table + '/' + id }); },
    signup: function (body) { return call({ method: 'POST', url: base + 'auth/signup', data: body }); },
    signin: function (body) { return call({ method: 'POST', url: base + 'auth/signin', data: body }); },
    signout: function () { return call({ method: 'POST', url: base + 'auth/signout' }); },
    me: function () { return call({ method: 'GET', url: base + 'auth/me' }); },
    authConfig: function () { return call({ method: 'GET', url: base + 'auth/config' }); },
    uploadPhoto: function (userId, file) {
      var form = new FormData();
      form.append('photo', file);
      return call({ method: 'PUT', url: base + 'users/' + userId + '/photo', data: form,
                    headers: { 'Content-Type': undefined }, transformRequest: angular.identity });
    },
    removePhoto: function (userId) { return call({ method: 'DELETE', url: base + 'users/' + userId + '/photo' }); }
  };
}]);
