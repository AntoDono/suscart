import { FaGithub } from 'react-icons/fa';
import { SiDevpost } from 'react-icons/si';
import './TopHeader.css';

const TopHeader = () => {
  return (
    <div className="top-header-container">
      <span className="header-spacer">·</span>
      <span className="header-spacer">✦</span>

      <a
        href="https://github.com/AntoDono/edgecart"
        target="_blank"
        rel="noopener noreferrer"
        className="header-icon header-icon-left"
      >
        <FaGithub />
      </a>

      <span className="header-spacer">✦</span>
      <span className="header-spacer">·</span>
      <span className="header-spacer">✦</span>

      <div className="mlh-logo">
        <img src="/mlh.png" alt="MLH" />
      </div>

      <span className="header-spacer">✦</span>
      <span className="header-spacer">·</span>
      <span className="header-spacer">✦</span>

      <a
        href="https://devpost.com/software/edgecart"
        target="_blank"
        rel="noopener noreferrer"
        className="header-icon header-icon-right"
      >
        <SiDevpost />
      </a>

      <span className="header-spacer">✦</span>
      <span className="header-spacer">·</span>
    </div>
  );
};

export default TopHeader;
