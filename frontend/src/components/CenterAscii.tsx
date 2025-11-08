import './CenterAscii.css';

const CenterAscii = () => {
  const asciiArt = `                   
     ▓▓▓▓▓▓▓▓▓▓▓    
 ███▒ ▓████████     
   ▓██▒▒█████▓ ██▒  
    ███▒▒███▒▒███   
    ▒███▓ █▒▒███▓   
     ████▓ ▒▓▓▓▒    
      █▓▒▒▒▒▒▒▒     
                    
       ██   ▒██     
                    `;

  return (
    <div className="center-ascii-container">
      <div className="star-pattern star-left">
        <span className="star-spacer">·</span>
        <span className="star-spacer">✦</span>
        <span className="star-spacer">·</span>
        <span className="star-spacer">✦</span>
        <span className="star-spacer">·</span>
        <span className="star-spacer">✦</span>
      </div>
      <pre className="center-ascii-art">{asciiArt}</pre>
      <div className="star-pattern star-right">
        <span className="star-spacer">✦</span>
        <span className="star-spacer">·</span>
        <span className="star-spacer">✦</span>
        <span className="star-spacer">·</span>
        <span className="star-spacer">✦</span>
        <span className="star-spacer">·</span>
      </div>
    </div>
  );
};

export default CenterAscii;
