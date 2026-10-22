import { Provider } from 'react-redux';
import { Toaster } from 'react-hot-toast';
import store from '@/store/store';
import '@/styles/globals.css';

export default function App({ Component, pageProps }) {
  return (
    <Provider store={store}>
      <Component {...pageProps} />
      <Toaster position="top-right" />
    </Provider>
  );
}
