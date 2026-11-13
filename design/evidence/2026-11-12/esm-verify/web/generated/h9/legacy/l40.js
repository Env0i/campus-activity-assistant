window.__esmOrder.push('l40');
window.__esmCount = (window.__esmCount || 0) + 1;

(function () {
  window.__legacyLayers = window.__legacyLayers || { state: {}, view: {}, controller: {} };
  window.__legacyLayers.state['40'] = { id: 40, name: 'state-40' };
  window.__legacyLayers.view['40'] = {
    render: function () { return 'card-' + window.__legacyLayers.state['40'].id; }
  };
  window.__legacyLayers.controller['40'] = {
    build: function () {
      return {
        id: window.__legacyLayers.state['40'].id,
        card: window.__legacyLayers.view['40'].render(),
        label: 'controller-40'
      };
    }
  };
})();

window.__esmDone = true;
window.__esmDoneAt = performance.now();
