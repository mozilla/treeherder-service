import angular from 'angular';
import ngRoute from 'angular-route';
import uiBootstrap from 'angular1-ui-bootstrap4';

import treeherderModule from './treeherder';

const treeherderApp = angular.module('treeherder.app', [
  treeherderModule.name,
  uiBootstrap,
  ngRoute,
]);

treeherderApp.config(['$compileProvider', '$locationProvider', '$routeProvider', '$httpProvider',
    function ($compileProvider, $locationProvider, $routeProvider, $httpProvider) {
        // Disable debug data & legacy comment/class directive syntax, as recommended by:
        // https://docs.angularjs.org/guide/production
        $compileProvider.debugInfoEnabled(false);
        $compileProvider.commentDirectivesEnabled(false);
        $compileProvider.cssClassDirectivesEnabled(false);

        // Revert to the legacy Angular <=1.5 URL hash prefix to save breaking existing links:
        // https://docs.angularjs.org/guide/migration#commit-aa077e8
        $locationProvider.hashPrefix('');

        $httpProvider.defaults.xsrfHeaderName = 'X-CSRFToken';
        $httpProvider.defaults.xsrfCookieName = 'csrftoken';
        $httpProvider.useApplyAsync(true);

        $routeProvider
            .when('/jobs', {
                // see controllers/main.js ``skipNextPageReload`` for
                // why we set this to false.
                reloadOnSearch: false,
            })
            .when('/jobs/:tree', {
                reloadOnSearch: false,
            })
            .otherwise({ redirectTo: '/jobs' });
    }]);

export default treeherderApp;
