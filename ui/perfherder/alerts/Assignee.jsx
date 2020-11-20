import React from 'react';
import PropTypes from 'prop-types';
import { Button, Input, InputGroup } from 'reactstrap';

export default class Assignee extends React.Component {
  constructor(props) {
    super(props);
    const { assigneeUsername } = props;

    this.state = {
      assigneeUsername,
      inEditMode: false,
      newAssigneeUsername: null,
      alertWatched: false,
    };
  }

  componentDidMount() {
    // React's onKeyPress isn't able to listen to 'Escape'.
    // This is a workaround.
    document.addEventListener('keydown', this.keydownListener);
  }

  componentWillUnmount() {
    document.removeEventListener('keydown', this.keydownListener);
  }

  goToEditMode = () => {
    const { user } = this.props;
    const { assigneeUsername } = this.state;

    if (user.isStaff) {
      this.setState({
        inEditMode: true,
        // input prefills with this field, so
        // we must have it prepared
        newAssigneeUsername: assigneeUsername,
      });
    }
  };

  editUsername = (newAssigneeUsername) => {
    this.setState({ newAssigneeUsername });
  };

  pressedEnter = async (event) => {
    event.preventDefault();
    if (event.key === 'Enter') {
      const { updateAssignee } = this.props;
      const newAssigneeUsername = event.target.value;

      const { failureStatus } = await updateAssignee(newAssigneeUsername);

      if (!failureStatus) {
        this.setState({
          assigneeUsername: newAssigneeUsername,
          inEditMode: false,
        });
      }
    }
  };

  prefillWithLoggedInUsername = () => {
    const { user } = this.props;

    this.setState({
      newAssigneeUsername: user.username,
      inEditMode: true,
    });
  };

  keydownListener = (event) => {
    if (event.key === 'Escape') {
      this.setState({ inEditMode: false });
    }
  };

  extractNicknameAndPlaceholder = (assigneeUsername) => {
    let nickname = 'Unassigned';
    const placeholder = 'nobody@mozilla.org';

    if (!assigneeUsername) {
      return { nickname, placeholder };
    }

    const nicknameRegex = /\/(\w+)@/g;
    // eslint-disable-next-line prefer-destructuring
    nickname = nicknameRegex.exec(assigneeUsername)[1];

    return { nickname, placeholder };
  };

  toggleAlertWatched = async () => {
    const { alertWatched } = this.state;
    if (alertWatched) {
      this.setState({ alertWatched: false });
      return;
    }
    if (!('Notification' in window)) {
      return;
    }
    let watchAlert = false;
    if (Notification.permission === 'granted') {
      watchAlert = true;
    } else if (Notification.permission !== 'denied') {
      Notification.requestPermission().then(permission => {
        if (permission === 'granted') {
          watchAlert = true;
        }
      });
    }
    this.setState({ alertWatched: watchAlert });
  };

  render() {
    const { user } = this.props;
    const {
      assigneeUsername,
      newAssigneeUsername,
      inEditMode,
      alertWatched,
    } = this.state;

    const { nickname, placeholder } = this.extractNicknameAndPlaceholder(
      assigneeUsername,
    );

    return !inEditMode ? (
      <React.Fragment>
        <Button
          className="ml-1"
          color="darker-secondary"
          size="xs"
          onClick={this.goToEditMode}
          title="Click to change assignee"
        >
          {nickname}
        </Button>
        {!assigneeUsername && (
          <Button
            className="ml-1"
            color="darker-secondary"
            size="xs"
            disabled={!user.isStaff}
            onClick={this.prefillWithLoggedInUsername}
          >
            Take
          </Button>
        )}
        <Button
          className="ml-1"
          color="darker-secondary"
          size="xs"
          onClick={this.toggleAlertWatched}
        >
          {alertWatched ? 'watched' : ' not watched'}
        </Button>
      </React.Fragment>
    ) : (
      <InputGroup size="sm">
        <Input
          disabled={!user.isStaff}
          placeholder={placeholder}
          value={newAssigneeUsername}
          aria-label="Set assignee"
          onChange={(event) => this.editUsername(event.target.value)}
          onKeyPress={(event) => this.pressedEnter(event)}
          autoFocus
        />
      </InputGroup>
    );
  }
}

Assignee.propTypes = {
  updateAssignee: PropTypes.func.isRequired,
  user: PropTypes.shape({}).isRequired,
  assigneeUsername: PropTypes.string,
};

Assignee.defaultProps = {
  assigneeUsername: null,
};
