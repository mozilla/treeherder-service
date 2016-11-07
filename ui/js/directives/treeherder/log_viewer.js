'use strict';

treeherder.directive('thLogViewer', ['$sce', '$location', ($sce, $location) => {
  return {
    restrict: "E",
    replace: true,
    link: function (scope, elem) {
      elem.on('load', () => {
        const q = $location.search();

        if (q.highlightStart !== 'undefined' && q.highlightStart) {
          scope.logPostMessage({ lineNumber: q.highlightStart });
        }
      });

      const searchPart = () => {
        const q = $location.search();

        return "&highlightStart=" + q.highlightStart + "&highlightEnd=" + q.highlightEnd + "&lineNumber="
          + q.lineNumber + "&wrapLines=" + q.wrapLines + "&showLineNumbers=" + q.showLineNumbers
          + "&jumpToHighlight=" + q.jumpToHighlight;
      };

      scope.$watch('rawLogURL', (rawLogURL) => {
        scope.logviewerURL = $sce.trustAsResourceUrl(`${scope.logBasePath}?url=${scope.rawLogURL}${searchPart()}`);
      });
    },
    templateUrl: 'partials/logviewer/logviewer.html'
  };
}]);
