/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */
// @flow

import * as React from 'react';
import { findDOMNode } from 'react-dom';

/**
 * Note: This component was taken from the Firefox Profiler. At the time of this writing
 * it has been used in production for years, and has been peer reviewed. It was modified
 * for the initial import by converting the type information into comments.
 *
 * https://github.com/firefox-devtools/profiler/blob/846ba69260e167a1a2a872a64ad1b7be0eba47bf/src/components/shared/WithSize.js
 *
 * Wraps a React component and makes 'width' and 'height' available in the
 * wrapped component's props. These props start out at zero and are updated to
 * the component's DOM node's getBoundingClientRect().width/.height after the
 * component has been mounted. They also get updated when the window is
 * resized.
 *
 * Note that the props are *not* updated if the size of the element changes
 * for reasons other than a window resize.
 */
export default function withSize(Wrapped) {
  return class WithSizeWrapper extends React.PureComponent {
    _isSizeInfoDirty = false;

    // The DOMNode of the container
    _container;

    constructor(props) {
      super(props);

      /**
       * @prop {number} width
       * @prop {number} height
       */
      this.state = { width: 0, height: 0 };
    }

    componentDidMount() {
      const container = findDOMNode(this); // eslint-disable-line react/no-find-dom-node
      if (!container) {
        throw new Error('Unable to find the DOMNode');
      }
      this._container = container;
      window.addEventListener('resize', this.resizeListener);
      window.addEventListener(
        'visibilitychange',
        this.visibilityChangeListener,
      );

      // Wrapping the first update in a requestAnimationFrame to defer the
      // calculation until the full render is done.
      requestAnimationFrame(() => {
        // This component could have already been unmounted, check for the existence
        // of the container.
        if (this._container) {
          this.updateWidth(this._container);
        }
      });
    }

    componentWillUnmount() {
      this._container = null;
      window.removeEventListener('resize', this.resizeListener);
      window.removeEventListener(
        'visibilitychange',
        this.visibilityChangeListener,
      );
    }

    // The size is only updated when the document is visible.
    // In other cases resizing is registered in _isSizeInfoDirty.
    resizeListener = () => {
      const container = this._container;
      if (!container) {
        return;
      }
      if (document.hidden) {
        this._isSizeInfoDirty = true;
      } else {
        this.updateWidth(container);
      }
    };

    // If resizing was registered when the document wasn't visible,
    // the size will be updated when the document becomes visible
    visibilityChangeListener = () => {
      const container = this._container;
      if (!container) {
        return;
      }
      if (!document.hidden && this._isSizeInfoDirty) {
        this.updateWidth(container);
        this._isSizeInfoDirty = false;
      }
    };

    /**
     * @param {HTMLElement | Text} container
     */
    updateWidth(container) {
      if (typeof container.getBoundingClientRect !== 'function') {
        throw new Error('Cannot measure a Text node.');
      }
      const { width, height } = container.getBoundingClientRect();
      this.setState({ width, height });
    }

    render() {
      return <Wrapped {...this.props} {...this.state} />;
    }
  };
}
