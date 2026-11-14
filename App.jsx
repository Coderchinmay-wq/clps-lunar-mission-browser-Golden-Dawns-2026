
import React from "react";
import MoonGlobe from "./components/MoonGlobe";
import "./App.css";

function App() {
  return (
    <div className="app">
      <header>
        <h1>CLPS Lunar Mission Browser</h1>
        <p>Explore the Moon. Discover landing sites. Plan lunar missions.</p>
      </header>

      <main>
        <h2>Interactive 3D Moon Explorer</h2>
        <MoonGlobe />
        <p className="instruction">
          Drag to rotate the Moon. Scroll to zoom in and out.
        </p>
      </main>
    </div>
  );
}

export default App;
