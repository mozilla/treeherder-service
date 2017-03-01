'use strict';

const merge = require('deepmerge');
const lintBase = require('neutrino-lint-base');
const path = require('path');

const CWD = process.cwd();
const UI = path.join(CWD, 'ui');

module.exports = neutrino => {
    lintBase(neutrino);
    neutrino.config.module
        .rule('lint')
        .include(UI)
        .test(/\.jsx?$/)
        .loader('eslint', props => merge(props, {
            options: {
                plugins: ['react'],
                envs: ['browser', 'es6', 'node'],
                parserOptions: {
                    sourceType: 'script',
                    ecmaFeatures: {
                        es6: true,
                        jsx: true,
                        impliedStrict: false
                    }
                },
                extends: 'eslint:recommended',
                rules: {
                    'accessor-pairs': 2,
                    'comma-style': 2,
                    'eol-last': 2,
                    'eqeqeq': 2,
                    'guard-for-in': 2,
                    'indent': [2, 4, {'SwitchCase': 1}],
                    'keyword-spacing': 2,
                    'linebreak-style': 2,
                    'new-cap': 2,
                    'new-parens': 2,
                    'no-array-constructor': 2,
                    'no-bitwise': 2,
                    'no-caller': 2,
                    'no-div-regex': 2,
                    'no-else-return': 2,
                    'no-empty-pattern': 2,
                    'no-eval': 2,
                    'no-extend-native': 2,
                    'no-extra-bind': 2,
                    'no-floating-decimal': 2,
                    'no-implied-eval': 2,
                    'no-iterator': 2,
                    'no-label-var': 2,
                    'no-labels': 2,
                    'no-lone-blocks': 2,
                    'no-lonely-if': 2,
                    'no-multi-spaces': 2,
                    'no-multi-str': 2,
                    'no-native-reassign': 2,
                    'no-new': 2,
                    'no-new-func': 2,
                    'no-new-object': 2,
                    'no-new-wrappers': 2,
                    'no-octal-escape': 2,
                    'no-proto': 2,
                    'no-return-assign': 2,
                    'no-script-url': 2,
                    'no-self-compare': 2,
                    'no-sequences': 2,
                    'no-shadow-restricted-names': 2,
                    'no-spaced-func': 2,
                    'no-trailing-spaces': 2,
                    'no-undef-init': 2,
                    'no-unexpected-multiline': 2,
                    'no-unused-expressions': 2,
                    'no-useless-call': 2,
                    'no-void': 2,
                    'no-with': 2,
                    'semi': 2,
                    'strict': [2, 'global'],
                    'yoda': 2
                },
                globals: [ 'angular', '$', '_', 'treeherder', 'jsyaml', 'perf',
                  'treeherderApp', 'failureViewerApp', 'logViewerApp',
                  'userguideApp', 'admin', 'Mousetrap', 'jQuery', 'React',
                  'hawk', 'jsonSchemaDefaults'
                ]
            }
        }));
};

