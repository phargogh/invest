import React from 'react';

import Alert from 'react-bootstrap/Alert';
import Button from 'react-bootstrap/Button';

import { handleClickFindLogfiles } from '../../menubar/handlers';

const logger = window.Workbench.getLogger('ErrorBoundary');

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    logger.error(error);
    logger.error(errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <Alert className="error-boundary">
          <h2>Something went wrong {String.fromCharCode(2)}</h2>
          <p>
            <em>Please help us fix this by reporting the problem.
            You may follow these steps:</em>
          </p>
          <ol>
            <li>
              <b>Find the Workbench log files</b> using the button below.
              There may be multiple files with a ".log" extension.
            </li>
            <Button
              onClick={handleClickFindLogfiles}
            >
              Find My Logs
            </Button>
            <br />
            <br />
            <li>
              <b>Create a post on our forum</b> and upload all the log files, along with a
              brief description of what happened before you saw this message.
              <br />
              <a
                href="https://community.naturalcapitalproject.org/"
              >
                https://community.naturalcapitalproject.org
              </a>
            </li>
          </ol>
        </Alert>
      );
    }
    return this.props.children;
  }
}
