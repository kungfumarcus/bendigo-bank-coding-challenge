interface StatusBannerProps {
  message: string;
  requestId?: string;
}

export function StatusBanner({ message, requestId }: StatusBannerProps) {
  return (
    <div className="banner" role="alert">
      <p>{message}</p>
      {requestId && <p className="reference">Reference: {requestId}</p>}
    </div>
  );
}
