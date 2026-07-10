import React from 'react';
import { BrowserRouter as Router, Route, Routes } from 'react-router-dom';
import UnrealContainer from './components/UnrealContainer';
import WeatherEngine from './components/layers/WeatherEngine';
import AmbientAI from './components/layers/AmbientAI';
import MainInterface from './components/MainInterface';
import DebugAdminLayer from './components/DebugAdminLayer';

const App: React.FC = () => {
  return (
    <Router>
      <div className="App">
        <UnrealContainer />
        <WeatherEngine />
        <AmbientAI />
        <MainInterface />
        <DebugAdminLayer />
      </div>
    </Router>
  );
};

export default App;