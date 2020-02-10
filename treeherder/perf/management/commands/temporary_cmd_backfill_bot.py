from django.core.management.base import BaseCommand

import jsone  # https://json-e.js.org/#Interface/python
import taskcluster

ROOT_URL = 'https://firefox-ci-tc.services.mozilla.com'
CREDENTIALS = {
    'clientId': 'asdf',
    'accessToken': 'qwerty'
}


# IMPORTANT NOTICE:
# This is basically a Pyhton redo of ui/models/taskcluster.js:TaskclusterModel.submit
# The method calls from `taskcluster` object were not adapted to Python's implementation.
# Please read the docs from https://github.com/taskcluster/taskcluster/tree/master/clients/client-py#readme


class Command(BaseCommand):
    help = "Pre-populate performance data from an external source"

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        index = taskcluster.Index({
            'rootUrl': ROOT_URL,
            'credentials': CREDENTIALS,
        })
        print(index.ping())

    def submit(self, action, actionTaskId,
               decisionTaskId, taskId, task,
               input, staticActionVariables, currentRepo):
        context = {'taskGroupId': decisionTaskId,
                   'taskId': taskId or None,
                   'input': input,
                   'staticActionVariables': staticActionVariables}
        queue = taskcluster.Queue({
            'rootUrl': ROOT_URL,
            'credentials': CREDENTIALS,
        })
        # More on https://docs.taskcluster.net/docs/manual/design/conventions/actions/ui
        if action.get('kind') == 'task':
            context.task = task
            context.ownTaskId = actionTaskId
            actionTask = jsone(action.task, context)
            decisionTask = queue.task(decisionTaskId)
            submitQueue = queue.use({'authorizedScopes': decisionTask.scopes})

            submitQueue.createTask(actionTaskId, actionTask)

            return actionTaskId

        if action.get('kind') == 'hook':
            hookPayload = jsone(action.hookPayload, context)
            hookId = action.get('hookId')
            hookGroupId = action.get('hookGroupId')

            auth = taskcluster.Auth({'rootUrl': currentRepo.tc_root_url})
            userCredentials = taskcluster.getCredentials(currentRepo.tc_root_url)
            if not userCredentials:
                raise Exception('Need to retrieve or renew Taskcluster credentials before action can be performed.')

            hooks = taskcluster.Hooks({'rootUrl': currentRepo.tc_root_url,
                                       'credentials': userCredentials.credentials, })
            decisionTask = queue.task(decisionTaskId)
            expansion = auth.expandScopes({'scopes': decisionTask.scopes})
            expression = 'in-tree:hook-action:{}/{}'.format(hookGroupId, hookId)

            # not sure if Python's taskcluster lib has a satisfiesExpression method.
            # Copied from JS, which takes it from 'taskcluster-lib-scopes'.
            if not taskcluster.satisfiesExpression(expansion.get('scopes', expression)):
                raise Exception("Action is misconfigured: decision task's scopes do not satisfy {}".format(expression))

            result = hooks.triggerHook(hookGroupId, hookId, hookPayload)
            return result.status.taskId


# just an example of actions.json
actions = {
    "actions": [
        {
            "context": [
                {
                    "test-type": "mochitest"
                },
                {
                    "test-type": "reftest"
                }
            ],
            "description": "Retriggers the specified mochitest/reftest job with additional options",
            "extra": {
                "actionPerm": "generic"
            },
            "hookGroupId": "project-gecko",
            "hookId": "in-tree-action-3-generic/9353e8f146",
            "hookPayload": {
                "decision": {
                    "action": {
                        "cb_name": "retrigger-mochitest",
                        "description": "Retriggers the specified mochitest/reftest job with additional options",
                        "name": "retrigger-mochitest",
                        "symbol": "rt",
                        "taskGroupId": "IModWhTtQlC8sCmKcwFIXA",
                        "title": "Retrigger Mochitest/Reftest with Debugging"
                    },
                    "push": {
                        "owner": "mozilla-taskcluster-maintenance@mozilla.com",
                        "pushlog_id": "106499",
                        "revision": "34f53b4b228420325f9af01a16e1ade33a245167"
                    },
                    "repository": {
                        "level": "3",
                        "project": "autoland",
                        "url": "https://hg.mozilla.org/integration/autoland"
                    }
                },
                "user": {
                    "input": {
                        "$eval": "input"
                    },
                    "taskGroupId": {
                        "$eval": "taskGroupId"
                    },
                    "taskId": {
                        "$eval": "taskId"
                    }
                }
            },
            "kind": "hook",
            "name": "retrigger-mochitest",
            "schema": {
                "additionalProperties": False,
                "properties": {
                    "environment": {
                        "additionalProperties": {
                            "type": "string"
                        },
                        "default": {
                            "MOZ_LOG": ""
                        },
                        "description": "Extra environment variables to use for this run",
                        "title": "Extra environment variables",
                        "type": "object"
                    },
                    "logLevel": {
                        "default": "debug",
                        "description": "Log level for output (default is DEBUG, which is highest)",
                        "enum": [
                            "debug",
                            "info",
                            "warning",
                            "error",
                            "critical"
                        ],
                        "title": "Log level",
                        "type": "string"
                    },
                    "path": {
                        "default": "",
                        "description": "Path of test to retrigger",
                        "maxLength": 255,
                        "title": "Path name",
                        "type": "string"
                    },
                    "preferences": {
                        "additionalProperties": {
                            "type": "string"
                        },
                        "default": {
                            "mygeckopreferences.pref": "myvalue2"
                        },
                        "description": "Extra gecko (about:config) preferences to use for this run",
                        "title": "Extra gecko (about:config) preferences",
                        "type": "object"
                    },
                    "repeat": {
                        "default": 30,
                        "description": "Run tests repeatedly (usually used in conjunction with runUntilFail)",
                        "minimum": 1,
                        "title": "Run tests N times",
                        "type": "integer"
                    },
                    "runUntilFail": {
                        "default": True,
                        "description": "Runs the specified set of tests repeatedly until failure (or 30 times)",
                        "title": "Run until failure",
                        "type": "boolean"
                    }
                },
                "required": [
                    "path"
                ],
                "type": "object"
            },
            "title": "Retrigger Mochitest/Reftest with Debugging"
        },
        {
            "context": [
                {
                    "kind": "decision-task"
                },
                {
                    "kind": "action-callback"
                },
                {
                    "kind": "cron-task"
                }
            ],
            "description": "Create a clone of the task (retriggering decision, action, and cron tasks requires\nspecial scopes).",
            "extra": {
                "actionPerm": "generic"
            },
            "hookGroupId": "project-gecko",
            "hookId": "in-tree-action-3-generic/9353e8f146",
            "hookPayload": {
                "decision": {
                    "action": {
                        "cb_name": "retrigger-decision",
                        "description": "Create a clone of the task (retriggering decision, action, and cron tasks requires\nspecial scopes).",
                        "name": "retrigger",
                        "symbol": "rt",
                        "taskGroupId": "IModWhTtQlC8sCmKcwFIXA",
                        "title": "Retrigger"
                    },
                    "push": {
                        "owner": "mozilla-taskcluster-maintenance@mozilla.com",
                        "pushlog_id": "106499",
                        "revision": "34f53b4b228420325f9af01a16e1ade33a245167"
                    },
                    "repository": {
                        "level": "3",
                        "project": "autoland",
                        "url": "https://hg.mozilla.org/integration/autoland"
                    }
                },
                "user": {
                    "input": {
                        "$eval": "input"
                    },
                    "taskGroupId": {
                        "$eval": "taskGroupId"
                    },
                    "taskId": {
                        "$eval": "taskId"
                    }
                }
            },
            "kind": "hook",
            "name": "retrigger",
            "title": "Retrigger"
        },
        {
            "context": [
                {
                    "retrigger": "true"
                }
            ],
            "description": "Create a clone of the task.",
            "extra": {
                "actionPerm": "generic"
            },
            "hookGroupId": "project-gecko",
            "hookId": "in-tree-action-3-generic/9353e8f146",
            "hookPayload": {
                "decision": {
                    "action": {
                        "cb_name": "retrigger",
                        "description": "Create a clone of the task.",
                        "name": "retrigger",
                        "symbol": "rt",
                        "taskGroupId": "IModWhTtQlC8sCmKcwFIXA",
                        "title": "Retrigger"
                    },
                    "push": {
                        "owner": "mozilla-taskcluster-maintenance@mozilla.com",
                        "pushlog_id": "106499",
                        "revision": "34f53b4b228420325f9af01a16e1ade33a245167"
                    },
                    "repository": {
                        "level": "3",
                        "project": "autoland",
                        "url": "https://hg.mozilla.org/integration/autoland"
                    }
                },
                "user": {
                    "input": {
                        "$eval": "input"
                    },
                    "taskGroupId": {
                        "$eval": "taskGroupId"
                    },
                    "taskId": {
                        "$eval": "taskId"
                    }
                }
            },
            "kind": "hook",
            "name": "retrigger",
            "schema": {
                "properties": {
                    "downstream": {
                        "default": False,
                        "description": "If true, downstream tasks from this one will be cloned as well. The dependencies will be updated to work with the new task at the root.",
                        "type": "boolean"
                    },
                    "times": {
                        "default": 1,
                        "description": "How many times to run each task.",
                        "maximum": 100,
                        "minimum": 1,
                        "title": "Times",
                        "type": "integer"
                    }
                },
                "type": "object"
            },
            "title": "Retrigger"
        },
        {
            "context": [
                {}
            ],
            "description": "Create a clone of the task.\n\nThis type of task should typically be re-run instead of re-triggered.",
            "extra": {
                "actionPerm": "generic"
            },
            "hookGroupId": "project-gecko",
            "hookId": "in-tree-action-3-generic/9353e8f146",
            "hookPayload": {
                "decision": {
                    "action": {
                        "cb_name": "retrigger-disabled",
                        "description": "Create a clone of the task.\n\nThis type of task should typically be re-run instead of re-triggered.",
                        "name": "retrigger",
                        "symbol": "rt",
                        "taskGroupId": "IModWhTtQlC8sCmKcwFIXA",
                        "title": "Retrigger (disabled)"
                    },
                    "push": {
                        "owner": "mozilla-taskcluster-maintenance@mozilla.com",
                        "pushlog_id": "106499",
                        "revision": "34f53b4b228420325f9af01a16e1ade33a245167"
                    },
                    "repository": {
                        "level": "3",
                        "project": "autoland",
                        "url": "https://hg.mozilla.org/integration/autoland"
                    }
                },
                "user": {
                    "input": {
                        "$eval": "input"
                    },
                    "taskGroupId": {
                        "$eval": "taskGroupId"
                    },
                    "taskId": {
                        "$eval": "taskId"
                    }
                }
            },
            "kind": "hook",
            "name": "retrigger",
            "schema": {
                "properties": {
                    "downstream": {
                        "default": False,
                        "description": "If true, downstream tasks from this one will be cloned as well. The dependencies will be updated to work with the new task at the root.",
                        "type": "boolean"
                    },
                    "force": {
                        "default": False,
                        "description": "This task should not be re-triggered. This can be overridden by passing `true` here.",
                        "type": "boolean"
                    },
                    "times": {
                        "default": 1,
                        "description": "How many times to run each task.",
                        "maximum": 100,
                        "minimum": 1,
                        "title": "Times",
                        "type": "integer"
                    }
                },
                "type": "object"
            },
            "title": "Retrigger (disabled)"
        },
        {
            "context": [
                {
                    "kind": "test",
                    "worker-implementation": "docker-worker"
                }
            ],
            "description": "Create a a copy of the task that you can interact with",
            "extra": {
                "actionPerm": "generic"
            },
            "hookGroupId": "project-gecko",
            "hookId": "in-tree-action-3-generic/9353e8f146",
            "hookPayload": {
                "decision": {
                    "action": {
                        "cb_name": "create-interactive",
                        "description": "Create a a copy of the task that you can interact with",
                        "name": "create-interactive",
                        "symbol": "create-inter",
                        "taskGroupId": "IModWhTtQlC8sCmKcwFIXA",
                        "title": "Create Interactive Task"
                    },
                    "push": {
                        "owner": "mozilla-taskcluster-maintenance@mozilla.com",
                        "pushlog_id": "106499",
                        "revision": "34f53b4b228420325f9af01a16e1ade33a245167"
                    },
                    "repository": {
                        "level": "3",
                        "project": "autoland",
                        "url": "https://hg.mozilla.org/integration/autoland"
                    }
                },
                "user": {
                    "input": {
                        "$eval": "input"
                    },
                    "taskGroupId": {
                        "$eval": "taskGroupId"
                    },
                    "taskId": {
                        "$eval": "taskId"
                    }
                }
            },
            "kind": "hook",
            "name": "create-interactive",
            "schema": {
                "additionalProperties": False,
                "properties": {
                    "notify": {
                        "default": "noreply@noreply.mozilla.org",
                        "description": "Enter your email here to get an email containing a link to interact with the task",
                        "format": "email",
                        "title": "Who to notify of the pending interactive task",
                        "type": "string"
                    }
                },
                "type": "object"
            },
            "title": "Create Interactive Task"
        },
        {
            "context": [],
            "description": "Add new jobs using task labels.",
            "extra": {
                "actionPerm": "generic"
            },
            "hookGroupId": "project-gecko",
            "hookId": "in-tree-action-3-generic/9353e8f146",
            "hookPayload": {
                "decision": {
                    "action": {
                        "cb_name": "add-new-jobs",
                        "description": "Add new jobs using task labels.",
                        "name": "add-new-jobs",
                        "symbol": "add-new",
                        "taskGroupId": "IModWhTtQlC8sCmKcwFIXA",
                        "title": "Add new jobs"
                    },
                    "push": {
                        "owner": "mozilla-taskcluster-maintenance@mozilla.com",
                        "pushlog_id": "106499",
                        "revision": "34f53b4b228420325f9af01a16e1ade33a245167"
                    },
                    "repository": {
                        "level": "3",
                        "project": "autoland",
                        "url": "https://hg.mozilla.org/integration/autoland"
                    }
                },
                "user": {
                    "input": {
                        "$eval": "input"
                    },
                    "taskGroupId": {
                        "$eval": "taskGroupId"
                    },
                    "taskId": {
                        "$eval": "taskId"
                    }
                }
            },
            "kind": "hook",
            "name": "add-new-jobs",
            "schema": {
                "properties": {
                    "tasks": {
                        "description": "An array of task labels",
                        "items": {
                            "type": "string"
                        },
                        "type": "array"
                    },
                    "times": {
                        "default": 1,
                        "description": "How many times to run each task.",
                        "maximum": 100,
                        "minimum": 1,
                        "title": "Times",
                        "type": "integer"
                    }
                },
                "type": "object"
            },
            "title": "Add new jobs"
        },
        {
            "context": [],
            "description": "Add all Talos tasks to a push.",
            "extra": {
                "actionPerm": "generic"
            },
            "hookGroupId": "project-gecko",
            "hookId": "in-tree-action-3-generic/9353e8f146",
            "hookPayload": {
                "decision": {
                    "action": {
                        "cb_name": "run-all-talos",
                        "description": "Add all Talos tasks to a push.",
                        "name": "run-all-talos",
                        "symbol": "raT",
                        "taskGroupId": "IModWhTtQlC8sCmKcwFIXA",
                        "title": "Run All Talos Tests"
                    },
                    "push": {
                        "owner": "mozilla-taskcluster-maintenance@mozilla.com",
                        "pushlog_id": "106499",
                        "revision": "34f53b4b228420325f9af01a16e1ade33a245167"
                    },
                    "repository": {
                        "level": "3",
                        "project": "autoland",
                        "url": "https://hg.mozilla.org/integration/autoland"
                    }
                },
                "user": {
                    "input": {
                        "$eval": "input"
                    },
                    "taskGroupId": {
                        "$eval": "taskGroupId"
                    },
                    "taskId": {
                        "$eval": "taskId"
                    }
                }
            },
            "kind": "hook",
            "name": "run-all-talos",
            "schema": {
                "additionalProperties": False,
                "properties": {
                    "times": {
                        "default": 1,
                        "description": "How many times to run each task.",
                        "maximum": 6,
                        "minimum": 1,
                        "title": "Times",
                        "type": "integer"
                    }
                },
                "type": "object"
            },
            "title": "Run All Talos Tests"
        },
        {
            "context": [
                {
                    "kind": "test"
                }
            ],
            "description": "Re-run Tests for original manifest, directories and tests for failing tests.",
            "extra": {
                "actionPerm": "generic"
            },
            "hookGroupId": "project-gecko",
            "hookId": "in-tree-action-3-generic/9353e8f146",
            "hookPayload": {
                "decision": {
                    "action": {
                        "cb_name": "isolate-test-failures",
                        "description": "Re-run Tests for original manifest, directories and tests for failing tests.",
                        "name": "isolate-test-failures",
                        "symbol": "it",
                        "taskGroupId": "IModWhTtQlC8sCmKcwFIXA",
                        "title": "Isolate test failures in job"
                    },
                    "push": {
                        "owner": "mozilla-taskcluster-maintenance@mozilla.com",
                        "pushlog_id": "106499",
                        "revision": "34f53b4b228420325f9af01a16e1ade33a245167"
                    },
                    "repository": {
                        "level": "3",
                        "project": "autoland",
                        "url": "https://hg.mozilla.org/integration/autoland"
                    }
                },
                "user": {
                    "input": {
                        "$eval": "input"
                    },
                    "taskGroupId": {
                        "$eval": "taskGroupId"
                    },
                    "taskId": {
                        "$eval": "taskId"
                    }
                }
            },
            "kind": "hook",
            "name": "isolate-test-failures",
            "schema": {
                "additionalProperties": False,
                "properties": {
                    "times": {
                        "default": 1,
                        "description": "How many times to run each task.",
                        "maximum": 100,
                        "minimum": 1,
                        "title": "Times",
                        "type": "integer"
                    }
                },
                "type": "object"
            },
            "title": "Isolate test failures in job"
        },
        {
            "context": [
                {}
            ],
            "description": "Take the label of the current task, and trigger the task with that label on previous pushes in the same project.",
            "extra": {
                "actionPerm": "generic"
            },
            "hookGroupId": "project-gecko",
            "hookId": "in-tree-action-3-generic/9353e8f146",
            "hookPayload": {
                "decision": {
                    "action": {
                        "cb_name": "backfill",
                        "description": "Take the label of the current task, and trigger the task with that label on previous pushes in the same project.",
                        "name": "backfill",
                        "symbol": "Bk",
                        "taskGroupId": "IModWhTtQlC8sCmKcwFIXA",
                        "title": "Backfill"
                    },
                    "push": {
                        "owner": "mozilla-taskcluster-maintenance@mozilla.com",
                        "pushlog_id": "106499",
                        "revision": "34f53b4b228420325f9af01a16e1ade33a245167"
                    },
                    "repository": {
                        "level": "3",
                        "project": "autoland",
                        "url": "https://hg.mozilla.org/integration/autoland"
                    }
                },
                "user": {
                    "input": {
                        "$eval": "input"
                    },
                    "taskGroupId": {
                        "$eval": "taskGroupId"
                    },
                    "taskId": {
                        "$eval": "taskId"
                    }
                }
            },
            "kind": "hook",
            "name": "backfill",
            "schema": {
                "additionalProperties": False,
                "properties": {
                    "depth": {
                        "default": 9,
                        "description": "The number of previous pushes before the current push to attempt to trigger this task on.",
                        "maximum": 25,
                        "minimum": 1,
                        "title": "Depth",
                        "type": "integer"
                    },
                    "inclusive": {
                        "default": False,
                        "description": "If true, the backfill will also retrigger the task on the selected push.",
                        "title": "Inclusive Range",
                        "type": "boolean"
                    },
                    "testPath": {
                        "title": "Test Path",
                        "type": "string"
                    },
                    "times": {
                        "default": 1,
                        "description": "The number of times to execute each job you are backfilling.",
                        "maximum": 10,
                        "minimum": 1,
                        "title": "Times",
                        "type": "integer"
                    }
                },
                "type": "object"
            },
            "title": "Backfill"
        },
        {
            "context": [
                {
                    "test-type": "talos"
                },
                {
                    "test-type": "raptor"
                }
            ],
            "description": "Take the label of the current task, and trigger the task with that label on previous pushes in the same project while adding the --geckoProfile cmd arg.",
            "extra": {
                "actionPerm": "generic"
            },
            "hookGroupId": "project-gecko",
            "hookId": "in-tree-action-3-generic/9353e8f146",
            "hookPayload": {
                "decision": {
                    "action": {
                        "cb_name": "geckoprofile",
                        "description": "Take the label of the current task, and trigger the task with that label on previous pushes in the same project while adding the --geckoProfile cmd arg.",
                        "name": "geckoprofile",
                        "symbol": "Gp",
                        "taskGroupId": "IModWhTtQlC8sCmKcwFIXA",
                        "title": "GeckoProfile"
                    },
                    "push": {
                        "owner": "mozilla-taskcluster-maintenance@mozilla.com",
                        "pushlog_id": "106499",
                        "revision": "34f53b4b228420325f9af01a16e1ade33a245167"
                    },
                    "repository": {
                        "level": "3",
                        "project": "autoland",
                        "url": "https://hg.mozilla.org/integration/autoland"
                    }
                },
                "user": {
                    "input": {
                        "$eval": "input"
                    },
                    "taskGroupId": {
                        "$eval": "taskGroupId"
                    },
                    "taskId": {
                        "$eval": "taskId"
                    }
                }
            },
            "kind": "hook",
            "name": "geckoprofile",
            "title": "GeckoProfile"
        },
        {
            "context": [],
            "description": "Run tests in the selected push that were optimized away, usually by SETA.\nThis action is for use on pushes that will be merged into another branch,to check that optimization hasn't hidden any failures.",
            "extra": {
                "actionPerm": "generic"
            },
            "hookGroupId": "project-gecko",
            "hookId": "in-tree-action-3-generic/9353e8f146",
            "hookPayload": {
                "decision": {
                    "action": {
                        "cb_name": "run-missing-tests",
                        "description": "Run tests in the selected push that were optimized away, usually by SETA.\nThis action is for use on pushes that will be merged into another branch,to check that optimization hasn't hidden any failures.",
                        "name": "run-missing-tests",
                        "symbol": "rmt",
                        "taskGroupId": "IModWhTtQlC8sCmKcwFIXA",
                        "title": "Run Missing Tests"
                    },
                    "push": {
                        "owner": "mozilla-taskcluster-maintenance@mozilla.com",
                        "pushlog_id": "106499",
                        "revision": "34f53b4b228420325f9af01a16e1ade33a245167"
                    },
                    "repository": {
                        "level": "3",
                        "project": "autoland",
                        "url": "https://hg.mozilla.org/integration/autoland"
                    }
                },
                "user": {
                    "input": {
                        "$eval": "input"
                    },
                    "taskGroupId": {
                        "$eval": "taskGroupId"
                    },
                    "taskId": {
                        "$eval": "taskId"
                    }
                }
            },
            "kind": "hook",
            "name": "run-missing-tests",
            "title": "Run Missing Tests"
        },
        {
            "context": [
                {}
            ],
            "description": "Rerun a task.\n\nThis only works on failed or exception tasks in the original taskgraph, and is CoT friendly.",
            "extra": {
                "actionPerm": "generic"
            },
            "hookGroupId": "project-gecko",
            "hookId": "in-tree-action-3-generic/9353e8f146",
            "hookPayload": {
                "decision": {
                    "action": {
                        "cb_name": "rerun",
                        "description": "Rerun a task.\n\nThis only works on failed or exception tasks in the original taskgraph, and is CoT friendly.",
                        "name": "rerun",
                        "symbol": "rr",
                        "taskGroupId": "IModWhTtQlC8sCmKcwFIXA",
                        "title": "Rerun"
                    },
                    "push": {
                        "owner": "mozilla-taskcluster-maintenance@mozilla.com",
                        "pushlog_id": "106499",
                        "revision": "34f53b4b228420325f9af01a16e1ade33a245167"
                    },
                    "repository": {
                        "level": "3",
                        "project": "autoland",
                        "url": "https://hg.mozilla.org/integration/autoland"
                    }
                },
                "user": {
                    "input": {
                        "$eval": "input"
                    },
                    "taskGroupId": {
                        "$eval": "taskGroupId"
                    },
                    "taskId": {
                        "$eval": "taskId"
                    }
                }
            },
            "kind": "hook",
            "name": "rerun",
            "schema": {
                "properties": {},
                "type": "object"
            },
            "title": "Rerun"
        },
        {
            "context": [
                {}
            ],
            "description": "Cancel the given task",
            "extra": {
                "actionPerm": "generic"
            },
            "hookGroupId": "project-gecko",
            "hookId": "in-tree-action-3-generic/9353e8f146",
            "hookPayload": {
                "decision": {
                    "action": {
                        "cb_name": "cancel",
                        "description": "Cancel the given task",
                        "name": "cancel",
                        "symbol": "cx",
                        "taskGroupId": "IModWhTtQlC8sCmKcwFIXA",
                        "title": "Cancel Task"
                    },
                    "push": {
                        "owner": "mozilla-taskcluster-maintenance@mozilla.com",
                        "pushlog_id": "106499",
                        "revision": "34f53b4b228420325f9af01a16e1ade33a245167"
                    },
                    "repository": {
                        "level": "3",
                        "project": "autoland",
                        "url": "https://hg.mozilla.org/integration/autoland"
                    }
                },
                "user": {
                    "input": {
                        "$eval": "input"
                    },
                    "taskGroupId": {
                        "$eval": "taskGroupId"
                    },
                    "taskId": {
                        "$eval": "taskId"
                    }
                }
            },
            "kind": "hook",
            "name": "cancel",
            "title": "Cancel Task"
        },
        {
            "context": [],
            "description": "Cancel all running and pending tasks created by the decision task this action task is associated with.",
            "extra": {
                "actionPerm": "generic"
            },
            "hookGroupId": "project-gecko",
            "hookId": "in-tree-action-3-generic/9353e8f146",
            "hookPayload": {
                "decision": {
                    "action": {
                        "cb_name": "cancel-all",
                        "description": "Cancel all running and pending tasks created by the decision task this action task is associated with.",
                        "name": "cancel-all",
                        "symbol": "cAll",
                        "taskGroupId": "IModWhTtQlC8sCmKcwFIXA",
                        "title": "Cancel All"
                    },
                    "push": {
                        "owner": "mozilla-taskcluster-maintenance@mozilla.com",
                        "pushlog_id": "106499",
                        "revision": "34f53b4b228420325f9af01a16e1ade33a245167"
                    },
                    "repository": {
                        "level": "3",
                        "project": "autoland",
                        "url": "https://hg.mozilla.org/integration/autoland"
                    }
                },
                "user": {
                    "input": {
                        "$eval": "input"
                    },
                    "taskGroupId": {
                        "$eval": "taskGroupId"
                    },
                    "taskId": {
                        "$eval": "taskId"
                    }
                }
            },
            "kind": "hook",
            "name": "cancel-all",
            "title": "Cancel All"
        },
        {
            "context": [
                {
                    "worker-implementation": "docker-worker"
                }
            ],
            "description": "Purge any caches associated with this task across all workers of the same workertype as the task.",
            "extra": {
                "actionPerm": "generic"
            },
            "hookGroupId": "project-gecko",
            "hookId": "in-tree-action-3-generic/9353e8f146",
            "hookPayload": {
                "decision": {
                    "action": {
                        "cb_name": "purge-cache",
                        "description": "Purge any caches associated with this task across all workers of the same workertype as the task.",
                        "name": "purge-cache",
                        "symbol": "purge-cache",
                        "taskGroupId": "IModWhTtQlC8sCmKcwFIXA",
                        "title": "Purge Worker Caches"
                    },
                    "push": {
                        "owner": "mozilla-taskcluster-maintenance@mozilla.com",
                        "pushlog_id": "106499",
                        "revision": "34f53b4b228420325f9af01a16e1ade33a245167"
                    },
                    "repository": {
                        "level": "3",
                        "project": "autoland",
                        "url": "https://hg.mozilla.org/integration/autoland"
                    }
                },
                "user": {
                    "input": {
                        "$eval": "input"
                    },
                    "taskGroupId": {
                        "$eval": "taskGroupId"
                    },
                    "taskId": {
                        "$eval": "taskId"
                    }
                }
            },
            "kind": "hook",
            "name": "purge-cache",
            "title": "Purge Worker Caches"
        },
        {
            "context": [],
            "description": "Action to prepare openh264 binaries for shipping",
            "extra": {
                "actionPerm": "generic"
            },
            "hookGroupId": "project-gecko",
            "hookId": "in-tree-action-3-generic/9353e8f146",
            "hookPayload": {
                "decision": {
                    "action": {
                        "cb_name": "openh264",
                        "description": "Action to prepare openh264 binaries for shipping",
                        "name": "openh264",
                        "symbol": "h264",
                        "taskGroupId": "IModWhTtQlC8sCmKcwFIXA",
                        "title": "OpenH264 Binaries"
                    },
                    "push": {
                        "owner": "mozilla-taskcluster-maintenance@mozilla.com",
                        "pushlog_id": "106499",
                        "revision": "34f53b4b228420325f9af01a16e1ade33a245167"
                    },
                    "repository": {
                        "level": "3",
                        "project": "autoland",
                        "url": "https://hg.mozilla.org/integration/autoland"
                    }
                },
                "user": {
                    "input": {
                        "$eval": "input"
                    },
                    "taskGroupId": {
                        "$eval": "taskGroupId"
                    },
                    "taskId": {
                        "$eval": "taskId"
                    }
                }
            },
            "kind": "hook",
            "name": "openh264",
            "title": "OpenH264 Binaries"
        },
        {
            "context": [],
            "description": "Create a clone of the task.",
            "extra": {
                "actionPerm": "generic"
            },
            "hookGroupId": "project-gecko",
            "hookId": "in-tree-action-3-generic/9353e8f146",
            "hookPayload": {
                "decision": {
                    "action": {
                        "cb_name": "retrigger-multiple",
                        "description": "Create a clone of the task.",
                        "name": "retrigger-multiple",
                        "symbol": "rt",
                        "taskGroupId": "IModWhTtQlC8sCmKcwFIXA",
                        "title": "Retrigger"
                    },
                    "push": {
                        "owner": "mozilla-taskcluster-maintenance@mozilla.com",
                        "pushlog_id": "106499",
                        "revision": "34f53b4b228420325f9af01a16e1ade33a245167"
                    },
                    "repository": {
                        "level": "3",
                        "project": "autoland",
                        "url": "https://hg.mozilla.org/integration/autoland"
                    }
                },
                "user": {
                    "input": {
                        "$eval": "input"
                    },
                    "taskGroupId": {
                        "$eval": "taskGroupId"
                    },
                    "taskId": {
                        "$eval": "taskId"
                    }
                }
            },
            "kind": "hook",
            "name": "retrigger-multiple",
            "schema": {
                "properties": {
                    "additionalProperties": False,
                    "requests": {
                        "items": {
                            "additionalProperties": False,
                            "tasks": {
                                "description": "An array of task labels",
                                "items": {
                                    "type": "string"
                                },
                                "type": "array"
                            },
                            "times": {
                                "description": "How many times to run each task.",
                                "maximum": 100,
                                "minimum": 1,
                                "title": "Times",
                                "type": "integer"
                            }
                        },
                        "type": "array"
                    }
                },
                "type": "object"
            },
            "title": "Retrigger"
        }
    ],
    "variables": {},
    "version": 1
}
