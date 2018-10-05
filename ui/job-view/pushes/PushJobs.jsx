import React from 'react';
import PropTypes from 'prop-types';

import { thPlatformMap, thSimplePlatforms, thEvents } from '../../helpers/constants';
import { withPinnedJobs } from '../context/PinnedJobs';
import { withSelectedJob } from '../context/SelectedJob';
import { getPushTableId } from '../../helpers/aggregateId';
import { findInstance, findSelectedInstance } from '../../helpers/job';
import { getUrlParam } from '../../helpers/location';
import { getLogViewerUrl } from '../../helpers/url';
import JobModel from '../../models/job';
import Platform from './Platform';

class PushJobs extends React.Component {
  static getDerivedStateFromProps(nextProps) {
    const { filterModel, push, platforms, runnableVisible } = nextProps;
    const selectedJobId = parseInt(getUrlParam('selectedJob'));
    const filteredPlatforms = platforms.reduce((acc, platform) => {
      const thisPlatform = { ...platform };
      const suffix = (thSimplePlatforms.includes(platform.name) && platform.option === 'opt') ? '' : ` ${platform.option}`;
      thisPlatform.title = `${thisPlatform.name}${suffix}`;
      thisPlatform.visible = true;
      return [...acc, PushJobs.filterPlatform(thisPlatform, selectedJobId, push, filterModel, runnableVisible)];
    }, []);

    return { filteredPlatforms };
  }

  static filterPlatform(platform, selectedJobId, push, filterModel) {
    platform.visible = false;
    platform.groups.forEach((group) => {
      group.visible = false;
      group.jobs.forEach((job) => {
        job.visible = filterModel.showJob(job) || job.id === selectedJobId;
        if (job.state === 'runnable') {
          job.visible = job.visible && push.isRunnableVisible;
        }
        job.selected = selectedJobId ? job.id === selectedJobId : false;
        if (job.visible) {
          platform.visible = true;
          group.visible = true;
        }
      });
    });
    return platform;
  }

  constructor(props) {
    super(props);
    const { $injector, push, repoName } = this.props;

    this.$rootScope = $injector.get('$rootScope');
    this.ThResultSetStore = $injector.get('ThResultSetStore');

    this.pushId = push.id;
    this.aggregateId = getPushTableId(
      repoName,
      this.pushId,
      push.revision,
    );

    this.onMouseDown = this.onMouseDown.bind(this);
    this.selectJob = this.selectJob.bind(this);
    this.filterPlatformCallback = this.filterPlatformCallback.bind(this);

    this.state = {
      isRunnableVisible: false,
      filteredPlatforms: [],
    };
  }

  componentDidMount() {
    this.applyNewJobsUnlisten = this.$rootScope.$on(
      thEvents.applyNewJobs, (ev, appliedpushId) => {
        if (appliedpushId === this.pushId) {
          this.applyNewJobs();
        }
      },
    );

    this.showRunnableJobsUnlisten = this.$rootScope.$on(thEvents.showRunnableJobs, (ev, pushId) => {
      const { push } = this.props;

      if (push.id === pushId) {
        push.isRunnableVisible = true;
        this.setState({ isRunnableVisible: true });
        this.ThResultSetStore.addRunnableJobs(push);
      }
    });

    this.deleteRunnableJobsUnlisten = this.$rootScope.$on(thEvents.deleteRunnableJobs, (ev, pushId) => {
      const { push } = this.props;

      if (push.id === pushId) {
        push.isRunnableVisible = false;
        this.setState({ isRunnableVisible: false });
        this.applyNewJobs();
      }
    });
  }

  componentWillUnmount() {
    this.applyNewJobsUnlisten();
    this.showRunnableJobsUnlisten();
    this.deleteRunnableJobsUnlisten();
  }

  onMouseDown(ev) {
    const { selectedJob, togglePinJob } = this.props;
    const jobInstance = findInstance(ev.target);

    if (jobInstance) {
      const job = jobInstance.props.job;
      if (ev.button === 1) { // Middle click
        this.handleLogViewerClick(job.id);
      } else if (ev.metaKey || ev.ctrlKey) { // Pin job
        if (!selectedJob) {
          this.selectJob(job, ev.target);
        }
        togglePinJob(job);
      } else if (job.state === 'runnable') { // Toggle runnable
        this.handleRunnableClick(jobInstance);
      } else {
        this.selectJob(job, ev.target); // Left click
      }
    }
  }

  // TODO: Remove when we convert restultsets_store
  getIdForPlatform(platform) {
    return getPlatformRowId(
      this.props.repoName,
      this.props.push.id,
      platform.name,
      platform.option,
    );
  }

  selectJob(job, el) {
    const { setSelectedJob, selectedJob } = this.props;
    if (selectedJob) {
      const selected = findSelectedInstance();
      if (selected) selected.setSelected(false);
    }
    const jobInstance = findInstance(el);
    jobInstance.setSelected(true);
    setSelectedJob(job);
  }

  applyNewJobs() {
    const { push, filterModel } = this.props;
    const selectedJobId = parseInt(getUrlParam('selectedJob'));

    if (!push.platforms) {
      return;
    }

    const rsPlatforms = push.platforms;
    const platforms = rsPlatforms.reduce((acc, platform) => {
      const thisPlatform = { ...platform };
      // TODO: don't need this ID once we re-work resultsets_store
      thisPlatform.id = this.getIdForPlatform(platform);
      thisPlatform.name = thPlatformMap[platform.name] || platform.name;
      const suffix = (thSimplePlatforms.includes(platform.name) && platform.option === 'opt') ? '' : ` ${platform.option}`;
      thisPlatform.title = `${thisPlatform.name}${suffix}`;
      thisPlatform.visible = true;
      return [...acc, PushJobs.filterPlatform(thisPlatform, selectedJobId, push, filterModel)];
    }, []);
    this.setState({ platforms });
  }

  handleLogViewerClick(jobId) {
    // Open logviewer in a new window
    const { repoName } = this.props;
    JobModel.get(
      repoName,
      jobId,
    ).then((data) => {
      if (data.logs.length > 0) {
        window.open(location.origin + '/' +
          getLogViewerUrl(jobId, repoName));
      }
    });
  }

  handleRunnableClick(job) {
    this.ThResultSetStore.toggleSelectedRunnableJob(
      this.pushId,
      job.ref_data_name,
    );
    findJobInstance(job.id, false).toggleRunnableSelected();
  }

  filterPlatformCallback(platform, selectedJobId) {
    const { push, filterModel } = this.props;
    const { filteredPlatforms } = this.state;

    // This actually filters the platform in-place.  So we just need to
    // trigger a re-render by giving it a new ``filteredPlatforms`` object instance.
    PushJobs.filterPlatform(platform, selectedJobId, push, filterModel, runnableVisible);
    if (filteredPlatforms.length) {
      this.setState({ filteredPlatforms: [...filteredPlatforms] });
    }
  }

  render() {
    const filteredPlatforms = this.state.filteredPlatforms || [];
    const { $injector, repoName, filterModel, pushGroupState } = this.props;

    return (
      <table id={this.aggregateId} className="table-hover" data-job-clear-on-click>
        <tbody onMouseDown={this.onMouseDown}>
          {filteredPlatforms ? filteredPlatforms.map(platform => (
          platform.visible &&
          <Platform
            platform={platform}
            repoName={repoName}
            $injector={$injector}
            key={platform.id}
            filterModel={filterModel}
            pushGroupState={pushGroupState}
            filterPlatformCb={this.filterPlatformCallback}
          />
        )) : <tr>
          <td><span className="fa fa-spinner fa-pulse th-spinner" /></td>
        </tr>}
        </tbody>
      </table>
    );
  }
}

PushJobs.propTypes = {
  push: PropTypes.object.isRequired,
  repoName: PropTypes.string.isRequired,
  filterModel: PropTypes.object.isRequired,
  togglePinJob: PropTypes.func.isRequired,
  $injector: PropTypes.object.isRequired,
  setSelectedJob: PropTypes.func.isRequired,
  pushGroupState: PropTypes.string.isRequired,
  selectedJob: PropTypes.object,
};

PushJobs.defaultProps = {
  selectedJob: null,
};

export default withSelectedJob(withPinnedJobs(PushJobs));
