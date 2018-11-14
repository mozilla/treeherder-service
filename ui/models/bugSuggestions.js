import { getProjectJobUrl } from '../helpers/url';

export default class BugSuggestionsModel {
  static get(jobId) {
    return fetch(getProjectJobUrl('/bug_suggestions/', jobId)).then(resp =>
      resp.json(),
    );
  }
}
