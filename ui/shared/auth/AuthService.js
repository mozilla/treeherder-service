import {
  userSessionFromAuthResult,
  renew,
  loggedOutUser,
} from '../../helpers/auth';
import taskcluster from '../../helpers/taskcluster';
import { getApiUrl } from '../../helpers/url';
import UserModel from '../../models/user';

const _fetchUser = function _fetchUser(userSession) {
  const loginUrl = getApiUrl('/auth/login/');

  // eslint-disable-next-line no-async-promise-executor
  return new Promise(async (resolve, reject) => {
    const userResponse = await fetch(loginUrl, {
      headers: {
        Authorization: `Bearer ${userSession.accessToken}`,
        'Access-Token-Expires-At': userSession.accessTokenExpiresAt,
        'Id-Token': userSession.idToken,
      },
      method: 'GET',
      credentials: 'same-origin',
    });

    const user = await userResponse.json();

    if (!userResponse.ok) {
      reject(new Error(user.detail || userResponse.statusText));
    }

    resolve(new UserModel(user));
  });
};

const saveCredentialsFromAuthResult = async function saveCredentialsFromAuthResult(
  authResult,
) {
  const userSession = userSessionFromAuthResult(authResult);
  const user = await _fetchUser(userSession);

  localStorage.setItem('userSession', JSON.stringify(userSession));
  localStorage.setItem('user', JSON.stringify(user));

  taskcluster.updateAgent();
};

const logout = function logout() {
  localStorage.removeItem('userSession');
  localStorage.setItem('user', JSON.stringify(loggedOutUser));
};

export default class AuthService {
  constructor() {
    this.renewalTimer = null;
  }

  _clearRenewalTimer() {
    if (this.renewalTimer) {
      clearTimeout(this.renewalTimer);
      this.renewalTimer = null;
    }
  }

  async _renewAuth() {
    try {
      if (!localStorage.getItem('userSession')) {
        return;
      }

      const authResult = await renew();

      if (authResult) {
        await saveCredentialsFromAuthResult(authResult);

        // eslint-disable-next-line consistent-return
        return this.resetRenewalTimer();
      }
    } catch (err) {
      // instance where a new scope was added and is now required in order to be logged in
      if (err.error === 'consent_required') {
        logout();
      }
      /* eslint-disable no-console */
      console.error('Could not renew login:', err);
    }
  }

  resetRenewalTimer() {
    const userSession = JSON.parse(localStorage.getItem('userSession'));

    // if a user has multiple treeherder tabs open and logs out from one of them,
    // we make sure to clear each tab's timer without renewing
    this._clearRenewalTimer();

    if (userSession) {
      let timeout = Math.max(0, new Date(userSession.renewAfter) - Date.now());

      // apply up to a few minutes to it randomly. This avoids
      // multiple tabs all trying to renew at the same time.
      if (timeout > 0) {
        timeout += Math.random() * 5 * 1000 * 60;
      }

      // create renewal timer
      this._clearRenewalTimer();
      this.renewalTimer = setTimeout(() => this._renewAuth(), timeout);
    }
  }
}
