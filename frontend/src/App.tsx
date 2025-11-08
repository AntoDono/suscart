import useIsMobile from './hooks/useIsMobile';
import MobileTerminal from './components/MobileTerminal';
import './App.css';

function App() {
  const isMobile = useIsMobile();

  return (
    <>
      {isMobile ? (
        <MobileTerminal />
      ) : (
        // Your existing desktop components can go here.
        // For now, it will be blank on desktop as per the previous request.
        null
      )}
    </>
  );
}

export default App;
