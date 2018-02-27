// Webpack entry point for perf.html
// Scripts and styles included here are automatically included on the page at build time

// Styles
require('bootstrap/dist/css/bootstrap.css');
require('font-awesome/css/font-awesome.css');
require('./css/treeherder-global.css');
require('./css/treeherder-navbar.css');
require('./css/perf.css');
require('./css/treeherder-loading-overlay.css');
require('metrics-graphics/dist/metricsgraphics.css');

// Vendor JS
require('angular');
require('angular-resource');
require('angular-ui-router');
require('angular-sanitize');
require('angular-local-storage');
require('mousetrap');
require('bootstrap/dist/js/bootstrap');
require('angular1-ui-bootstrap4');
require('angular-clipboard');
// The official 'flot' NPM package is out of date, so we're using 'jquery.flot'
// instead, which is identical to https://github.com/flot/flot
require('jquery.flot');
require('jquery.flot/jquery.flot.time.js');
require('jquery.flot/jquery.flot.selection.js');

// Bootstrap the Angular modules against which everything will be registered
require('./js/perf.js');

// Perf JS
require('./js/services/treestatus.js');
require('./js/providers.js');
require('./js/values.js');
require('./js/filters.js');
require('./js/models/option_collection.js');
require('./js/services/main.js');
require('./js/services/taskcluster.js');
require('./js/models/repository.js');
require('./js/models/job.js');
require('./js/models/runnable_job.js');
require('./js/models/resultset.js');
require('./js/services/tcactions.js');
require('./js/models/user.js');
require('./js/models/error.js');
require('./js/models/perf/series.js');
require('./js/models/perf/performance_framework.js');
require('./js/models/perf/alerts.js');
require('./js/services/perf/math.js');
require('./js/services/perf/compare.js');
require('./js/controllers/perf/compare.js');
require('./js/controllers/perf/graphs.js');
require('./js/controllers/perf/alerts.js');
require('./js/controllers/perf/dashboard.js');
require('./js/components/perf/compare.js');
require('./js/components/auth.js');
require('./js/components/loading.js');
require('./js/perfapp.js');
require('./js/filters.js');
