declare module 'papaparse' {
  interface ParseError {
    message: string;
  }

  interface ParseResult<T> {
    data: T[];
    errors: ParseError[];
  }

  interface ParseConfig {
    header?: boolean;
    dynamicTyping?: boolean;
    skipEmptyLines?: boolean;
    transformHeader?: (header: string) => string;
  }

  const Papa: {
    parse<T = unknown>(input: string, config?: ParseConfig): ParseResult<T>;
  };

  export default Papa;
}
