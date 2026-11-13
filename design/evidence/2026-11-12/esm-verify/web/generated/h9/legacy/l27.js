window.__esmOrder.push('l27');
window.__esmCount = (window.__esmCount || 0) + 1;

(function () {
  window.__legacyLayers = window.__legacyLayers || { state: {}, view: {}, controller: {} };
  window.__legacyLayers.state['27'] = { id: 27, name: 'state-27' };
  window.__legacyLayers.view['27'] = {
    render: function () { return 'card-' + window.__legacyLayers.state['27'].id; }
  };
  window.__legacyLayers.controller['27'] = {
    build: function () {
      return {
        id: window.__legacyLayers.state['27'].id,
        card: window.__legacyLayers.view['27'].render(),
        label: 'controller-27'
      };
    }
  };
})();
