import './BottomAscii.css';

const BottomAscii = () => {
  const centerArt = `
  
                                        .                                              .                                
      .                        .     .  .      ..  .      .                                         .             .   
                  .        .           .      .       .      .       .      .                   .  .
                                     .          .        .      .    .      .                  .  .   .      .     
             .       .      .            .      .      .        .      .                       .             .      .                            .        . ..     . .      . .
  .      .     .  .             .              .      .       .   .           .   .      .
    .     .        .     .  .       .      .         .      .                                   .      .             .           . .        .
        .       .       .     .            .   .  .    ..          . ..    . .    .             .   .   .    . ..              .   . . ... .    .`;

  return (
    <div className="bottom-ascii-container">
      <div className="ascii-content">
        <pre className="ascii-center">{centerArt}</pre>
      </div>
    </div>
  );
};

export default BottomAscii;
