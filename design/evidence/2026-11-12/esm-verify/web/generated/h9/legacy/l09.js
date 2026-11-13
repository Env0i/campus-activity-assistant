window.__esmOrder.push('l09');
window.__esmCount = (window.__esmCount || 0) + 1;

(function () {
  window.__legacyLayers = window.__legacyLayers || { state: {}, view: {}, controller: {} };
  window.__legacyLayers.state['09'] = { id: 9, name: 'state-09' };
  window.__legacyLayers.view['09'] = {
    render: function () { return 'card-' + window.__legacyLayers.state['09'].id; }
  };
  window.__legacyLayers.controller['09'] = {
    build: function () {
      return {
        id: window.__legacyLayers.state['09'].id,
        card: window.__legacyLayers.view['09'].render(),
        label: 'controller-09'
      };
    }
  };
})();
