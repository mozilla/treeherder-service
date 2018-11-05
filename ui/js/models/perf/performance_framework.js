// Remove the eslint-disable when rewriting this file during the React conversion.
/* eslint-disable object-shorthand */
import treeherder from '../../treeherder';
import { getApiUrl } from '../../../helpers/url';

treeherder.factory(
    'PhFramework', [
        '$http',
        function ($http) {
            return {
                getFrameworkList: function () {
                    return $http.get(getApiUrl('/performance/framework/'))
                      .then(function (response) {
                        return response.data;
                      });
                },
            };
        }]);
