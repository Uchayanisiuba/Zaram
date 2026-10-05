/**
 * @vitest-environment jsdom
 *
 * Every outcome of running a page is a sentence under the reply, including the
 * ones that are not good news.
 */
import { afterEach, describe, expect, it } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import PageCheckLine from './PageCheckLine';
import { replyKey, usePageCheckStore, type PageCheckState } from '@/stores/pageCheckStore';

const reply = '```html\n<p>x</p>\n```';

function show(state: PageCheckState | null) {
  act(() => {
    usePageCheckStore.setState({ byReply: state ? { [replyKey(reply)]: state } : {}, enabled: true });
  });
  return render(<PageCheckLine reply={reply} />);
}

afterEach(() => cleanup());

describe('the line under a page reply', () => {
  it('says nothing about a reply that was not checked', () => {
    show(null);
    expect(screen.queryByTestId('page-check')).toBeNull();
  });

  it('says it is running', () => {
    show({ status: 'checking', note: '', attempt: 0, slowSeconds: 0 });
    expect(screen.getByTestId('page-check').textContent).toContain('Running the page');
  });

  it('says a clean page ran without errors, and does not claim more', () => {
    show({ status: 'clean', note: '', attempt: 0, slowSeconds: 0 });
    expect(screen.getByTestId('page-check').textContent).toContain('Ran without errors.');
  });

  it('says how long a page held still, and that the figure came from a machine with no GPU', () => {
    show({ status: 'clean', note: '', attempt: 0, slowSeconds: 8.7 });
    const text = screen.getByTestId('page-check').textContent ?? '';
    expect(text).toContain('8.7 seconds');
    expect(text).toContain('without a graphics card');
  });

  it('names the problem and the try it is on', () => {
    show({ status: 'fixing', note: 'startTheGame is not defined', attempt: 1, slowSeconds: 0 });
    const text = screen.getByTestId('page-check').textContent ?? '';
    expect(text).toContain('startTheGame is not defined');
    expect(text).toContain('try 1 of 2');
  });

  it('hands over after the last fix, pointing at what to do', () => {
    show({ status: 'gave-up', note: 'still broken', attempt: 2, slowSeconds: 0 });
    const text = screen.getByTestId('page-check').textContent ?? '';
    expect(text).toContain('Still not running after 2 fixes');
    expect(text).toContain('Fix this');
  });

  it('says a page that could not be run was not checked, with the reason', () => {
    show({ status: 'unchecked', note: 'No Chrome or Edge is installed', attempt: 0, slowSeconds: 0 });
    const text = screen.getByTestId('page-check').textContent ?? '';
    expect(text).toContain('Not checked');
    expect(text).toContain('No Chrome');
    expect(text).not.toContain('without errors');
  });

  it('can be turned off from the line itself', () => {
    show({ status: 'clean', note: '', attempt: 0, slowSeconds: 0 });
    fireEvent.click(screen.getByText('Turn off'));
    expect(usePageCheckStore.getState().enabled).toBe(false);
  });
});
