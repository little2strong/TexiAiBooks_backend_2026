import React from 'react';
import whyDidYouRender from '@welldone-software/why-did-you-render';
// Explicit opt-in only. Never log financial values, tokens, or component props.
whyDidYouRender(React, { trackAllPureComponents: true, notifier: info => console.debug(`[render diagnostic] ${info.displayName}`) });
