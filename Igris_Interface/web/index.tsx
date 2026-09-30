import React from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import { ContextMenuLayer, installGlobalMenuBlock } from './components/ContextMenu';
import './index.css';

// Native brauzer o'ng-tugma menyusini bloklaymiz (input/textarea'da ruxsat beriladi)
installGlobalMenuBlock();

// Mount React app
const container = document.getElementById('root');
if (container) {
  const root = createRoot(container);
  root.render(
    <React.StrictMode>
      <ContextMenuLayer>
        <App />
      </ContextMenuLayer>
    </React.StrictMode>,
  );
}
