import Head from 'next/head';
import { Provider } from 'react-redux';
import { Toaster } from 'react-hot-toast';
import store from '@/store/store';
import '@/styles/globals.css';

export default function App({ Component, pageProps }) {
  return (
    <Provider store={store}>
      <Head>
        <link rel="shortcut icon" href="/favicon.ico" key="shortcut-icon" />
        <link rel="icon" href="/favicon.ico" sizes="32x32" key="favicon" />
        <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png" key="favicon-32" />
        <link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png" key="favicon-16" />
        <link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png" key="apple-touch-icon" />
      </Head>
      <Component {...pageProps} />
      <Toaster position="top-right" />
    </Provider>
  );
}
