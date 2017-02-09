"use strict";

treeherder.controller('BugFilerCtrl', [
    '$scope', '$rootScope', '$uibModalInstance', '$http', 'summary', 'thBugzillaProductObject',
    'thPinboard', 'thEvents', 'fullLog', 'parsedLog', 'reftest', 'selectedJob', 'allFailures',
    'thNotify',
    function BugFilerCtrl(
        $scope, $rootScope, $uibModalInstance, $http, summary, thBugzillaProductObject,
        thPinboard, thEvents, fullLog, parsedLog, reftest, selectedJob, allFailures,
        thNotify) {

        var bzBaseUrl = "https://bugzilla.mozilla.org/";

        $scope.omittedLeads = ["TEST-UNEXPECTED-FAIL", "PROCESS-CRASH", "TEST-UNEXPECTED-ERROR"];

        /**
         *  'enter' from the product search input should initiate the search
         */
        $scope.productSearchEnter = function(ev) {
            if (ev.keyCode === 13) {
                $scope.findProduct();
            }
        };

        /*
         **
         */
        $scope.isReftest = function() {
            return reftest !== "";
        };

        $scope.parsedLog = parsedLog;
        $scope.fullLog = fullLog;
        if ($scope.isReftest()) {
            $scope.reftest = reftest;
        }

        /**
         *  Pre-fill the form with information/metadata from the failure
         */
        $scope.initiate = function() {
            thPinboard.pinJob($rootScope.selectedJob);
            var thisFailure = "";
            for (var i = 0; i < allFailures.length; i++) {
                for (var j=0; j < $scope.omittedLeads.length; j++) {
                    if (allFailures[i][0].search($scope.omittedLeads[j]) >= 0 && allFailures[i].length > 1) {
                        allFailures[i].shift();
                    }
                }
                if (i !== 0) {
                    thisFailure += "\n";
                }
                thisFailure += allFailures[i].join(" | ");
            }
            $scope.thisFailure = thisFailure;

            $scope.findProduct();
        };

        $uibModalInstance.parsedSummary = "";
        $uibModalInstance.initiate = $scope.initiate;
        $uibModalInstance.possibleFilename = "";

        /*
         *  Remove extraneous junk from the start of the summary line
         *  and try to find the failing test name from what's left
         */
        $uibModalInstance.parseSummary = function(summary) {
            summary = summary.split(" | ");

            for (var i=0; i < $scope.omittedLeads.length; i++) {
                if (summary[0].search($scope.omittedLeads[i]) >= 0 && summary.length > 1) {
                    summary.shift();
                }
            }

            $uibModalInstance.possibleFilename = summary[0].split("/").pop();

            return [summary, $uibModalInstance.possibleFilename];
        };

        $uibModalInstance.parsedSummary = $uibModalInstance.parseSummary(summary);
        $scope.modalSummary = "Intermittent " + $uibModalInstance.parsedSummary[0].join(" | ");

        $scope.toggleFilerSummaryVisibility = function() {
            $scope.isFilerSummaryVisible = !$scope.isFilerSummaryVisible;
        };

        $scope.isFilerSummaryVisible = false;

        /*
         *  Attempt to find a good product/component for this failure
         */
        $scope.findProduct = function() {
            $scope.suggestedProducts = [];
            var failurePath = $uibModalInstance.parsedSummary[0][0];

            // If the "TEST-UNEXPECTED-foo" isn't one of the omitted ones, use the next piece in the summary
            if (failurePath.includes("TEST-UNEXPECTED-")) {
                failurePath = $uibModalInstance.parsedSummary[0][1];
            }
            var failurePathRoot = failurePath.split("/")[0];

            // Look up the product via the root of the failure's file path
            if (thBugzillaProductObject[failurePathRoot]) {
                $scope.suggestedProducts.push(thBugzillaProductObject[failurePathRoot][0]);
            }

            // Some job types are special, lets explicitly handle them.
            if (selectedJob.job_group_name.includes("Web Platform")) {
                $scope.suggestedProducts.push("Testing :: web-platform-tests");
            }

            // Look up product suggestions via Bugzilla's api
            var productSearch = $scope.productSearch;

            if (productSearch) {
                $http.get(bzBaseUrl + "rest/prod_comp_search/" + productSearch + "?limit=5").then(function(request) {
                    var data = request.data;
                    // We can't file unless product and component are provided, this api can return just product. Cut those out.
                    for (var i = data.products.length - 1; i >= 0; i--) {
                        if (!data.products[i].component) {
                            data.products.splice(i, 1);
                        }
                    }
                    $scope.suggestedProducts = [];
                    $scope.suggestedProducts = _.map(data.products, function(prod) {
                        if (prod.product && prod.component) {
                            return prod.product + " :: " + prod.component;
                        }
                        return prod.product;
                    });
                    $scope.selection.selectedProduct = $scope.suggestedProducts[0];
                });
            }

            $scope.selection.selectedProduct = $scope.suggestedProducts[0];
        };

        /*
         *  Same as clicking outside of the modal, but with a nice button-clicking feel...
         */
        $scope.cancelFiler = function() {
            $uibModalInstance.dismiss('cancel');
        };

        $scope.checkedLogLinks = {
            parsedLog: $scope.parsedLog,
            fullLog: $scope.fullLog,
            reftest: $scope.reftest
        };

        $scope.isIntermittent = true;

        /*
         *  Actually send the gathered information to bugzilla.
         */
        $scope.submitFiler = function() {
            var summarystring = $scope.modalSummary;
            var productString = "";
            var componentString = "";

            $scope.toggleForm(true);

            if ($scope.modalSummary.length > 255) {
                thNotify.send("Please ensure the summary is no more than 255 characters", "danger");
                $scope.toggleForm(false);
                return;
            }

            if ($scope.selection.selectedProduct) {
                var prodParts = $scope.selection.selectedProduct.split(" :: ");
                productString += prodParts[0];
                componentString += prodParts[1];
            } else {
                thNotify.send("Please select (or search and select) a product/component pair to continue", "danger");
                $scope.toggleForm(false);
                return;
            }

            var descriptionStrings = _.reduce($scope.checkedLogLinks, function(result, link) {
                if (link) {
                    result = result + link + "\n\n";
                }
                return result;
            }, "");
            if ($scope.modalComment) {
                descriptionStrings += $scope.modalComment;
            }

            var keywords = $scope.isIntermittent ? "intermittent-failure" : "";

            var blocks = $scope.modalBlocks;
            var dependsOn = $scope.modalDependsOn;
            var seeAlso = $scope.modalSeeAlso;

            // Fetch product information from bugzilla to get version numbers, then submit the new bug
            // Only request the versions because some products take quite a long time to fetch the full object
            $http.get(bzBaseUrl + "rest/product/" + productString + "?include_fields=versions")
                .then(function(response) {
                    var productJSON = response.data;
                    var productObject = productJSON.products[0];

                    // Find the newest version for the product that is_active
                    var version = _.findLast(productObject.versions, function(version) {
                        return version.is_active === true;
                    });

                    return $http({
                        url: "api/bugzilla/create_bug/",
                        method: "POST",
                        data: {
                            "product": productString,
                            "component": componentString,
                            "summary": summarystring,
                            "keywords": keywords,
                            "version": version.name,
                            "blocks": blocks,
                            "depends_on": dependsOn,
                            "see_also": seeAlso,
                            "comment": descriptionStrings,
                            "comment_tags": "treeherder"
                        }
                    });
                })
                .then((response) => {
                    var data = response.data;
                    if (data.failure) {
                        var error = JSON.parse(data.failure.join(""));
                        thNotify.send("Bugzilla error: " + error.message, "danger", true);
                        $scope.toggleForm(false);
                    } else {
                        // Auto-classify this failure now that the bug has been filed and we have a bug number
                        thPinboard.addBug({id: data.success});
                        $rootScope.$evalAsync($rootScope.$emit(thEvents.saveClassification));

                        // Open the newly filed bug in a new tab or window for further editing
                        window.open(bzBaseUrl + "show_bug.cgi?id=" + data.success);
                        $scope.cancelFiler();
                    }
                })
                .catch((response) => {
                    var failureString = "Bug Filer API returned status " + response.status + " (" + response.statusText + ")";
                    if (response.data && response.data.failure) {
                        failureString += "\n\n" + response.data.failure;
                    }
                    if (response.status === 403) {
                        failureString += "\n\nAuthentication failed. Has your Treeherder session expired?";
                    }
                    thNotify.send(failureString, "danger");
                    $scope.toggleForm(false);
                });
        };

        /*
         *  Disable or enable form elements as needed at various points in the submission process
         */
        $scope.toggleForm = function(disabled) {
            $(':input','#modalForm').attr("disabled", disabled);
        };
    }
]);

