// Karma/webpack entry for tests

// Global variables are set here instead of with webpack.ProvidePlugin
// because neutrino removes plugin definitions for karma runs
window.$ = require('jquery');
window.jQuery = require('jquery');
window._ = require('lodash');
window.angular = require('angular');
window.React = require('react');
require('jasmine-jquery');
require('angular-mocks');
require('angular-resource');
require('angular-route');
require('angular-sanitize');
require('angular-local-storage');
require('angular-toarrayfilter');
require('mousetrap');
require('ngreact');
require('angular1-ui-bootstrap4');
require('angular-marked');
require('../../../ui/vendor/resizer.js');

const Adapter = require('enzyme-adapter-react-16');
const Enzyme = require('enzyme');

Enzyme.configure({ adapter: new Adapter() });

const jsContext = require.context('../../../ui/js', true, /^\.\/.*\.jsx?$/);
window.SERVICE_DOMAIN = process.env.SERVICE_DOMAIN || '';
jsContext('./values.js');
jsContext('./providers.js');
jsContext('./filters.js');

const controllerContext = require.context('../../../ui/js/controllers', true, /^\.\/.*\.jsx?$/);
controllerContext.keys().forEach(controllerContext);
const directiveContext = require.context('../../../ui/js/directives', true, /^\.\/.*\.jsx?$/);
directiveContext.keys().forEach(directiveContext);
const modelContext = require.context('../../../ui/js/models', true, /^\.\/.*\.jsx?$/);
modelContext.keys().forEach(modelContext);
const serviceContext = require.context('../../../ui/js/services', true, /^\.\/.*\.jsx?$/);
serviceContext.keys().forEach(serviceContext);
const componentContext = require.context('../../../ui/js/components', true, /^\.\/.*\.jsx?$/);
componentContext.keys().forEach(componentContext);
const pluginContext = require.context('../../../ui/plugins', true, /^\.\/.*\.jsx?$/);
pluginContext.keys().forEach(pluginContext);

const testContext = require.context('./', true, /^\.\/.*\.tests\.jsx?$/);
testContext.keys().forEach(testContext);
